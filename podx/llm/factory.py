"""Factory for creating LLM provider instances."""

import os
from typing import Dict, Optional, Type

from ..logging import get_logger
from .base import LLMProvider, LLMProviderError

logger = get_logger(__name__)

# Global registry of provider classes
_PROVIDER_REGISTRY: Dict[str, Type[LLMProvider]] = {}


def register_provider(name: str, provider_class: Type[LLMProvider]) -> None:
    """Register a provider class.

    Args:
        name: Provider name (e.g., 'openai', 'anthropic')
        provider_class: Provider class to register
    """
    _PROVIDER_REGISTRY[name.lower()] = provider_class
    logger.debug(f"Registered LLM provider: {name}")


def get_provider(
    name: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs,
) -> LLMProvider:
    """Get a provider instance by name.

    Args:
        name: Provider name (openai, anthropic, openrouter, ollama)
        api_key: Optional API key (falls back to env vars)
        base_url: Optional base URL override
        **kwargs: Additional provider-specific parameters

    Returns:
        Configured provider instance

    Raises:
        LLMProviderError: If provider not found or initialization fails

    Example:
        >>> provider = get_provider("openai", api_key="sk-...")
        >>> response = provider.complete(
        ...     messages=[LLMMessage.user("Hello!")],
        ...     model="gpt-4"
        ... )
    """
    name = name.lower()

    if name not in _PROVIDER_REGISTRY:
        raise LLMProviderError(
            f"Provider '{name}' not found. Available providers: "
            f"{', '.join(_PROVIDER_REGISTRY.keys())}"
        )

    provider_class = _PROVIDER_REGISTRY[name]

    # Auto-detect API keys from environment if not provided
    if api_key is None:
        api_key = _get_api_key_for_provider(name)

    # Auto-detect base URL from environment if not provided
    if base_url is None:
        base_url = _get_base_url_for_provider(name)

    try:
        return provider_class(api_key=api_key, base_url=base_url, **kwargs)
    except Exception as e:
        raise LLMProviderError(f"Failed to initialize provider '{name}': {e}") from e


def _get_api_key_for_provider(name: str) -> Optional[str]:
    """Get API key from environment variables for a provider.

    Args:
        name: Provider name

    Returns:
        API key from environment, or None
    """
    # Map provider names to common environment variable names
    env_var_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "ollama": None,  # Ollama doesn't require API key
    }

    env_var = env_var_map.get(name)
    if env_var:
        return os.getenv(env_var)
    return None


def _get_base_url_for_provider(name: str) -> Optional[str]:
    """Get base URL from environment variables for a provider.

    Args:
        name: Provider name

    Returns:
        Base URL from environment, or None
    """
    # Map provider names to base URL environment variables
    env_var_map = {
        "openai": "OPENAI_BASE_URL",
        "anthropic": "ANTHROPIC_BASE_URL",
        "openrouter": "OPENROUTER_BASE_URL",
        "ollama": "OLLAMA_BASE_URL",
    }

    env_var = env_var_map.get(name)
    if env_var:
        return os.getenv(env_var)
    return None


# Auto-register built-in providers on import
def _register_builtin_providers():
    """Register all built-in providers."""
    try:
        from .openai_provider import OpenAIProvider

        register_provider("openai", OpenAIProvider)
    except ImportError:
        logger.debug("OpenAI provider not available (openai library not installed)")

    try:
        from .anthropic_provider import AnthropicProvider

        register_provider("anthropic", AnthropicProvider)
    except ImportError:
        logger.debug("Anthropic provider not available (anthropic library not installed)")

    try:
        from .openrouter_provider import OpenRouterProvider

        register_provider("openrouter", OpenRouterProvider)
    except ImportError:
        logger.debug("OpenRouter provider not available")

    try:
        from .ollama_provider import OllamaProvider

        register_provider("ollama", OllamaProvider)
    except ImportError:
        logger.debug("Ollama provider not available")


_register_builtin_providers()
