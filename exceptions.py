"""Custom exceptions for the Plex Summary Updater."""


class PlexSummaryUpdaterError(Exception):
    """Base exception for all application errors."""


class TMDBError(PlexSummaryUpdaterError):
    """Raised when TMDB API requests fail."""


class PlexError(PlexSummaryUpdaterError):
    """Raised when Plex operations fail."""


class ConfigError(PlexSummaryUpdaterError):
    """Raised when configuration is invalid or missing."""
