"""Factory for creating diarization provider instances.

This implements the Factory pattern to create providers dynamically,
combined with a registry pattern to allow plugin-style provider registration.
"""

from typing import Any, Callable, Dict, Optional, Type

from ...logging import get_logger
from .base import DiarizationConfig, DiarizationProvider, DiarizationProviderError
from .local_provider import LocalDiarizationProvider
from .runpod_provider import RunPodDiarizationProvider

logger = get_logger(__name__)

# Registry of available providers
_PROVIDER_REGISTRY: Dict[str, Type[DiarizationProvider]] = {
    "local": LocalDiarizationProvider,
    "runpod": RunPodDiarizationProvider,
}


def register_provider(name: str, provider_class: Type[DiarizationProvider]) -> None:
    """Register a new diarization provider.

    This enables a plugin architecture where third-party providers can be
    registered at runtime without modifying PodX code.

    Args:
        name: Provider identifier (e.g., "custom", "azure")
        provider_class: Provider class that implements DiarizationProvider interface

    Example:
        >>> class CustomProvider(DiarizationProvider):
        ...     def diarize(self, audio_path, transcript_segments):
        ...         # Your implementation
        ...         pass
        >>>
        >>> register_provider("custom", CustomProvider)
        >>> provider = get_diarization_provider("custom")
    """
    if not issubclass(provider_class, DiarizationProvider):
        raise ValueError(f"Provider class {provider_class} must inherit from DiarizationProvider")

    _PROVIDER_REGISTRY[name] = provider_class
    logger.info(f"Registered diarization provider: {name}")


def get_diarization_provider(
    provider_name: str,
    language: str = "en",
    device: Optional[str] = None,
    hf_token: Optional[str] = None,
    num_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
    **extra_options: Any,
) -> DiarizationProvider:
    """Factory function to create a diarization provider instance.

    Args:
        provider_name: Provider identifier ("local", "runpod")
        language: Language code for alignment (default: "en")
        device: Device to use (None for auto-detect)
        hf_token: Hugging Face token for pyannote models
        num_speakers: Exact number of speakers (if known)
        min_speakers: Minimum number of speakers
        max_speakers: Maximum number of speakers
        progress_callback: Optional callback for progress updates
        **extra_options: Additional provider-specific options

    Returns:
        Configured diarization provider instance

    Raises:
        DiarizationProviderError: If provider name is unknown

    Example:
        >>> provider = get_diarization_provider("local", language="en", num_speakers=2)
        >>> result = provider.diarize(audio_path, transcript_segments)
    """
    provider_class = _PROVIDER_REGISTRY.get(provider_name)

    if provider_class is None:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise DiarizationProviderError(
            f"Unknown diarization provider: {provider_name}. Available: {available}"
        )

    config = DiarizationConfig(
        language=language,
        device=device,
        hf_token=hf_token,
        num_speakers=num_speakers,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
        progress_callback=progress_callback,
        extra_options=extra_options,
    )

    return provider_class(config)


def list_providers() -> Dict[str, Type[DiarizationProvider]]:
    """Get all registered providers.

    Returns:
        Dictionary mapping provider names to provider classes
    """
    return _PROVIDER_REGISTRY.copy()
