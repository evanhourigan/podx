"""Cloud storage integration for audio and transcript files."""

from .manager import StorageBackend, StorageError, StorageManager

__all__ = [
    "StorageBackend",
    "StorageError",
    "StorageManager",
]
