"""Configuration settings for the Plex Summary Updater."""

from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration settings."""

    plex_url: str
    plex_token: str
    tmdb_api_key: str
    max_workers: int = 10
    verify_ssl: bool = False
    tmdb_base_url: str = "https://api.themoviedb.org/3"
