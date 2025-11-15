"""LLM provider abstraction for multi-provider support.

This module provides a unified interface for different LLM providers:
- OpenAI (GPT-4, GPT-3.5, etc.)
- Anthropic (Claude)
- OpenRouter (multi-model aggregator)
- Ollama (local models)

Usage:
    from podx.llm import get_provider, OpenAIProvider

    provider = get_provider("openai")
    response = provider.complete(
        messages=[{"role": "user", "content": "Hello!"}],
        model="gpt-4"
    )
"""

from .base import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
)
from .factory import get_provider, register_provider
from .mock import MockLLMProvider
from .openai_provider import OpenAIProvider

__all__ = [
    # Base
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    # Errors
    "LLMProviderError",
    "LLMAuthenticationError",
    "LLMRateLimitError",
    "LLMAPIError",
    # Factory
    "get_provider",
    "register_provider",
    # Providers
    "OpenAIProvider",
    "MockLLMProvider",
]
