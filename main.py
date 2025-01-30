"""Updates Plex library summaries with data from TMDB.

This module provides functionality to automatically update movie and TV show summaries
in a Plex Media Server library using data from The Movie Database (TMDB).

The module supports multithreaded processing and provides real-time progress tracking.
It first attempts to match content using TMDB IDs stored in Plex metadata, falling
back to title-based search if no ID is found.

Typical usage:
    $ python main.py

The script requires environment variables for authentication:
    PLEX_URL: URL of your Plex server
    PLEX_TOKEN: Your Plex authentication token
    TMDB_API_KEY: Your TMDB API key
"""

from __future__ import annotations

import logging
import os
from concurrent import futures
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import urllib3
from dotenv import load_dotenv
from plexapi.server import PlexServer
from plexapi.video import Movie, Show
from tqdm import tqdm

from config import Config
from exceptions import ConfigError, PlexError, TMDBError

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Type aliases
MediaItem = Union[Movie, Show]
UpdateResult = Tuple[str, str]
TMDBData = Dict[str, Any]

# Disable SSL warnings for corporate environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

# Initialize TMDB configuration
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Initialize Plex
PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
plex = PlexServer(PLEX_URL, PLEX_TOKEN)

# Configure max workers for thread pool
MAX_WORKERS = 10


class PlexSummaryUpdater:
    """Handles updating Plex media summaries with TMDB data."""

    def __init__(self, config: Config):
        """Initialize the updater with configuration.

        Args:
            config: Application configuration settings.

        Raises:
            ConfigError: If required configuration is missing.
        """
        self.config = config
        self._validate_config()

        if not config.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.plex = self._init_plex()
        self.session = self._init_tmdb_session()

    def _validate_config(self) -> None:
        """Validate required configuration settings are present."""
        required = ["plex_url", "plex_token", "tmdb_api_key"]
        missing = [field for field in required if not getattr(self.config, field)]
        if missing:
            raise ConfigError(f"Missing required configuration: {', '.join(missing)}")

    def _init_plex(self) -> PlexServer:
        """Initialize Plex server connection."""
        try:
            return PlexServer(self.config.plex_url, self.config.plex_token)
        except Exception as e:
            raise PlexError(f"Failed to connect to Plex: {e}") from e

    def _init_tmdb_session(self) -> requests.Session:
        """Initialize TMDB API session."""
        session = requests.Session()
        session.params = {"api_key": self.config.tmdb_api_key}
        return session

    @lru_cache(maxsize=1024)
    def _make_tmdb_request_cached(
        self, endpoint: str, param_items: tuple = ()
    ) -> Optional[TMDBData]:
        """Makes a cached request to the TMDB API.

        Internal method that handles the actual caching. Only used for
        requests with hashable parameters.

        Args:
            endpoint: The TMDB API endpoint to request.
            param_items: Tuple of (key, value) pairs for request parameters.

        Returns:
            The JSON response data if successful.

        Raises:
            TMDBError: If the API request fails.
        """
        try:
            url = f"{self.config.tmdb_base_url}/{endpoint}"
            params = dict(param_items) if param_items else {}
            response = self.session.get(url, params=params, verify=self.config.verify_ssl)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise TMDBError(f"TMDB API request failed: {e}") from e

    def make_tmdb_request(self, endpoint: str, **kwargs) -> Optional[TMDBData]:
        """Makes a request to the TMDB API.

        Public method that handles both cached and uncached requests.

        Args:
            endpoint: The TMDB API endpoint to request.
            **kwargs: Additional arguments for requests.get().

        Returns:
            The JSON response data if successful.

        Raises:
            TMDBError: If the API request fails.
        """
        # Extract params from kwargs
        params = kwargs.pop("params", {})

        # If we have additional kwargs, use uncached version
        if kwargs:
            try:
                url = f"{self.config.tmdb_base_url}/{endpoint}"
                response = self.session.get(
                    url, params=params, verify=self.config.verify_ssl, **kwargs
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                raise TMDBError(f"TMDB API request failed: {e}") from e

        # For simple params-only requests, use cached version
        # Convert params dict items to tuple for hashing
        param_items = tuple(sorted(params.items()))
        return self._make_tmdb_request_cached(endpoint, param_items)

    def update_library(self) -> None:
        """Update summaries for all supported media in Plex libraries."""
        for section in self.plex.library.sections():
            if section.type not in ("movie", "show"):
                continue

            logger.info("Processing %s Library", section.title)
            results = self._process_section(section)

            if not results:
                continue

            self._log_results(section.title, results)

    def _process_section(self, section) -> List[UpdateResult]:
        """Process all items in a library section using thread pool."""
        media_items = list(section.all())
        results = []

        with futures.ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_title = {
                executor.submit(self._update_item, item): item.title for item in media_items
            }

            with tqdm(
                total=len(media_items),
                desc=f"Processing {section.title}",
                unit=f"{section.type}s",
                leave=False,
            ) as pbar:
                for future in futures.as_completed(future_to_title):
                    try:
                        result = future.result()
                        results.append(result)
                        pbar.update(1)
                        pbar.set_postfix_str(f"Last: {result[0][:30]}...")
                    except Exception:
                        logger.exception("Error processing item")

        return results

    def _update_item(self, media_item: MediaItem) -> UpdateResult:
        """Update a single media item's summary."""
        try:
            tmdb_data = self._get_tmdb_data(media_item)
            if not tmdb_data:
                return media_item.title, "No TMDB match found"

            if media_item.summary != tmdb_data["overview"]:
                media_item.edit(**{"summary.value": tmdb_data["overview"]})
                return media_item.title, "Updated"
            return media_item.title, "No change needed"

        except Exception as e:
            logger.exception("Error updating %s", media_item.title)
            return media_item.title, f"Error: {str(e)}"

    def _get_tmdb_data(self, media_item: MediaItem) -> Optional[TMDBData]:
        """Fetches metadata from TMDB for a given media item.

        First attempts to use the TMDB ID from Plex metadata, then falls back to
        searching by title if no ID is found.

        Args:
            media_item: The Plex media item to fetch data for.

        Returns:
            The TMDB metadata if found, None otherwise.

        Raises:
            TMDBError: If the TMDB API request fails.
        """
        tmdb_id = self._get_tmdb_id(media_item)
        if not tmdb_id:
            return self._search_tmdb(media_item)

        media_type = "movie" if media_item.type == "movie" else "tv"
        return self.make_tmdb_request(f"{media_type}/{tmdb_id}")

    def _search_tmdb(self, media_item: MediaItem) -> Optional[TMDBData]:
        """Searches TMDB for a media item by title and year.

        Args:
            media_item: The Plex media item to search for.

        Returns:
            The first matching TMDB result if found, None otherwise.

        Raises:
            TMDBError: If the TMDB API request fails.
        """
        media_type = "movie" if media_item.type == "movie" else "tv"
        params = {"query": media_item.title, "year": getattr(media_item, "year", None)}

        response = self.make_tmdb_request(f"search/{media_type}", params=params)
        if not response:
            return None

        results = response.get("results", [])
        return next(iter(results), None)

    def _get_tmdb_id(self, media_item: MediaItem) -> Optional[str]:
        """Extracts TMDB ID from Plex media item metadata.

        Args:
            media_item: The Plex media item to extract ID from.

        Returns:
            The TMDB ID if found, None otherwise.
        """
        for guid in media_item.guids:
            if "tmdb" in guid.id:
                return guid.id.replace("tmdb://", "")
        return None

    @staticmethod
    def _log_results(section_title: str, results: List[UpdateResult]) -> None:
        """Log summary of update results in a concise format.

        Args:
            section_title: Title of the processed library section.
            results: List of (title, status) tuples from processing.
        """
        total = len(results)
        updated = sum(1 for _, status in results if status == "Updated")
        percentage = (updated / total * 100) if total > 0 else 0

        logger.info("%s Changed: %d/%d (%.1f%%)", section_title, updated, total, percentage)


def main() -> None:
    """Main entry point for the script."""
    load_dotenv()

    try:
        config = Config(
            plex_url=os.getenv("PLEX_URL", ""),
            plex_token=os.getenv("PLEX_TOKEN", ""),
            tmdb_api_key=os.getenv("TMDB_API_KEY", ""),
        )

        updater = PlexSummaryUpdater(config)
        updater.update_library()

    except Exception as e:
        logger.exception("Fatal error")
        raise SystemExit(f"Error: {e}") from e


if __name__ == "__main__":
    main()
