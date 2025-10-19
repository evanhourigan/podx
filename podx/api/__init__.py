"""Public API for podx - High-level interface for podcast processing.

This package provides a clean, type-safe API for integrating podx into other applications.

Basic usage:
    >>> from podx.api import PodxClient
    >>> client = PodxClient()
    >>> result = client.transcribe("https://example.com/audio.mp3", model="base")
    >>> print(result.transcript_path)

Advanced usage with configuration:
    >>> from podx.api import PodxClient, ClientConfig
    >>> config = ClientConfig(default_model="medium", cache_enabled=True)
    >>> client = PodxClient(config=config)
    >>> result = client.transcribe_and_analyze("audio.mp3")
"""

from .client import ClientConfig, PodxClient
from .models import (
    APIError,
    DeepcastResponse,
    ExistsCheckResponse,
    TranscribeResponse,
    ValidationResult,
)

__all__ = [
    "PodxClient",
    "ClientConfig",
    "TranscribeResponse",
    "DeepcastResponse",
    "ExistsCheckResponse",
    "APIError",
    "ValidationResult",
]
