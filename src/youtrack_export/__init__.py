from importlib.metadata import version, PackageNotFoundError
"""
YouTrack Export Application Package
"""

try:
    __version__ = version('youtrack-export')
except PackageNotFoundError:
    __version__ = 'unknown'