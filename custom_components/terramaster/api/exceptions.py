"""Exceptions raised by the TerraMaster API."""


class TerraMasterError(Exception):
    """Base TerraMaster API exception."""


class TerraMasterConnectionError(TerraMasterError):
    """Raised when the SSH connection fails."""


class TerraMasterAuthenticationError(TerraMasterError):
    """Raised when SSH authentication fails."""


class TerraMasterHostKeyError(TerraMasterError):
    """Raised when the server host key has changed."""


class TerraMasterCommandError(TerraMasterError):
    """Raised when a remote collection command fails."""
