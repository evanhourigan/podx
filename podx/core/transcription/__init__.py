"""Transcription providers using Strategy pattern.

This module implements the Strategy pattern for ASR (Automatic Speech Recognition) providers,
enabling easy addition of new providers without modifying existing code (Open/Closed Principle).

Usage:
    from podx.core.transcription import get_provider, LocalProvider, OpenAIProvider

    provider = get_provider("local", model="large-v3")
    result = provider.transcribe(audio_path)
"""

from .base import ASRProvider, ProviderConfig, TranscriptionResult
from .factory import get_provider, list_providers, register_provider
from .local_provider import LocalProvider
from .openai_provider import OpenAIProvider

__all__ = [
    # Base classes
    "ASRProvider",
    "ProviderConfig",
    "TranscriptionResult",
    # Providers
    "LocalProvider",
    "OpenAIProvider",
    # Factory
    "get_provider",
    "register_provider",
    "list_providers",
]
