"""Factory for creating ASR provider instances.

This implements the Factory pattern to create providers dynamically,
combined with a registry pattern to allow plugin-style provider registration.
"""

from typing import Dict, Optional, Type

from ...logging import get_logger
from .base import ASRProvider, ProviderConfig, TranscriptionError
from .local_provider import LocalProvider
from .openai_provider import OpenAIProvider

logger = get_logger(__name__)

# Registry of available providers
_PROVIDER_REGISTRY: Dict[str, Type[ASRProvider]] = {
    "local": LocalProvider,
    "openai": OpenAIProvider,
}


def register_provider(name: str, provider_class: Type[ASRProvider]) -> None:
    """Register a new ASR provider.

    This enables a plugin architecture where third-party providers can be
    registered at runtime without modifying PodX code.

    Args:
        name: Provider identifier (e.g., "anthropic", "google", "azure")
        provider_class: Provider class that implements ASRProvider interface

    Example:
        >>> class CustomProvider(ASRProvider):
        ...     def transcribe(self, audio_path):
        ...         # Your implementation
        ...         pass
        >>>
        >>> register_provider("custom", CustomProvider)
        >>> provider = get_provider("custom", model="my-model")
    """
    if not issubclass(provider_class, ASRProvider):
        raise ValueError(
            f"Provider class {provider_class} must inherit from ASRProvider"
        )

    _PROVIDER_REGISTRY[name] = provider_class
    logger.info(f"Registered ASR provider: {name}")


def get_provider(
    provider_name: str,
    model: str,
    device: Optional[str] = None,
    compute_type: Optional[str] = None,
    language: str = "en",
    vad_filter: bool = True,
    condition_on_previous_text: bool = True,
    **extra_options,
) -> ASRProvider:
    """Factory function to create an ASR provider instance.

    Args:
        provider_name: Provider identifier ("local", "openai", "hf")
        model: Model identifier
        device: Device to use (None for auto-detect)
        compute_type: Compute type (None for auto-detect)
        language: Language code
        vad_filter: Enable voice activity detection
        condition_on_previous_text: Enable conditioning on previous text
        **extra_options: Additional provider-specific options

    Returns:
        Configured ASR provider instance

    Raises:
        TranscriptionError: If provider name is unknown

    Example:
        >>> provider = get_provider("local", model="large-v3", device="cuda")
        >>> result = provider.transcribe(audio_path)
    """
    provider_class = _PROVIDER_REGISTRY.get(provider_name)

    if provider_class is None:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise TranscriptionError(
            f"Unknown ASR provider: {provider_name}. Available: {available}"
        )

    config = ProviderConfig(
        model=model,
        device=device,
        compute_type=compute_type,
        language=language,
        vad_filter=vad_filter,
        condition_on_previous_text=condition_on_previous_text,
        extra_options=extra_options,
    )

    return provider_class(config)


def list_providers() -> Dict[str, Type[ASRProvider]]:
    """Get all registered providers.

    Returns:
        Dictionary mapping provider names to provider classes
    """
    return _PROVIDER_REGISTRY.copy()
