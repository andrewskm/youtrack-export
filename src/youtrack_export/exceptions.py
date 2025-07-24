"""
Custom exceptions for YouTrack client.
"""

class YouTrackError(Exception):
    """Base exception for YouTrack client errors."""
    pass

class AuthenticationError(YouTrackError):
    """Raised when authentication fails."""
    pass

class APIError(YouTrackError):
    """Raised when API requests fail."""
    pass