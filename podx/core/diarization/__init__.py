"""Diarization provider abstraction for PodX.

Provides a Strategy pattern interface for diarization backends,
allowing seamless switching between local (pyannote) and cloud (RunPod)
processing.

Usage:
    # Local diarization (default)
    from podx.core.diarization import get_diarization_provider
    provider = get_diarization_provider("local", language="en")
    result = provider.diarize(audio_path, transcript_segments)

    # Cloud diarization
    provider = get_diarization_provider("runpod", language="en")
    result = provider.diarize(audio_path, transcript_segments)
"""

from .base import (
    DiarizationConfig,
    DiarizationProvider,
    DiarizationProviderError,
    DiarizationResult,
)
from .factory import get_diarization_provider, list_providers, register_provider
from .local_provider import LocalDiarizationProvider
from .runpod_provider import RunPodDiarizationProvider

__all__ = [
    # Base classes
    "DiarizationConfig",
    "DiarizationProvider",
    "DiarizationProviderError",
    "DiarizationResult",
    # Providers
    "LocalDiarizationProvider",
    "RunPodDiarizationProvider",
    # Factory
    "get_diarization_provider",
    "list_providers",
    "register_provider",
]
