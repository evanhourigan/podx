"""OpenRouter LLM provider implementation.

OpenRouter is a unified API that provides access to multiple LLM providers
(OpenAI, Anthropic, Google, Meta, Mistral, etc.) through a single interface.
"""

import os
from typing import Any, List, Optional

from ..logging import get_logger
from .base import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
)

logger = get_logger(__name__)


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider for multi-model access.

    OpenRouter provides access to models from multiple providers:
    - OpenAI (GPT-4, GPT-3.5)
    - Anthropic (Claude 3, Claude 2)
    - Google (Gemini, PaLM)
    - Meta (Llama 2, Llama 3)
    - Mistral (Mistral 7B, Mixtral)
    - And many more

    Uses OpenAI-compatible API, so we can use the OpenAI SDK.
    """

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        app_name: Optional[str] = None,
    ):
        """Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            base_url: Optional base URL override (defaults to openrouter.ai)
            app_name: Optional app name for OpenRouter tracking

        Raises:
            LLMProviderError: If openai library not installed or API key missing
        """
        try:
            from openai import AsyncOpenAI, OpenAI
        except ImportError:
            raise LLMProviderError("openai library not installed. Install with: pip install openai")

        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", self.OPENROUTER_BASE_URL)
        self.app_name = app_name or "PodX"

        if not self.api_key:
            raise LLMAuthenticationError(
                "OpenRouter API key not found. Set OPENROUTER_API_KEY environment variable "
                "or pass api_key parameter. Get key at: https://openrouter.ai/keys"
            )

        # Initialize both sync and async clients with OpenRouter base URL
        # OpenRouter uses OpenAI-compatible API
        default_headers = {
            "HTTP-Referer": "https://github.com/evandempsey/podx",
            "X-Title": self.app_name,
        }

        self._sync_client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=default_headers,
        )
        self._async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=default_headers,
        )

        logger.debug("Initialized OpenRouter provider")

    def complete(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion from messages (synchronous).

        Args:
            messages: List of conversation messages
            model: Model identifier (e.g., 'anthropic/claude-3-opus')
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenRouter API parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMAuthenticationError: If API key is invalid
            LLMRateLimitError: If rate limit exceeded
            LLMAPIError: If API returns an error

        Note:
            OpenRouter model names use format: provider/model-name
            Examples: anthropic/claude-3-opus, openai/gpt-4, meta-llama/llama-2-70b
        """
        try:
            response = self._sync_client.chat.completions.create(
                model=model,
                messages=[msg.to_dict() for msg in messages],  # type: ignore[misc]
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage=(
                    {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                    if response.usage
                    else None
                ),
                raw_response=response,
            )

        except Exception as e:
            return self._handle_error(e)

    async def complete_async(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion from messages (asynchronous).

        Args:
            messages: List of conversation messages
            model: Model identifier (e.g., 'anthropic/claude-3-opus')
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenRouter API parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMAuthenticationError: If API key is invalid
            LLMRateLimitError: If rate limit exceeded
            LLMAPIError: If API returns an error
        """
        try:
            response = await self._async_client.chat.completions.create(
                model=model,
                messages=[msg.to_dict() for msg in messages],  # type: ignore[misc]
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage=(
                    {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                    if response.usage
                    else None
                ),
                raw_response=response,
            )

        except Exception as e:
            return self._handle_error(e)

    def supports_streaming(self) -> bool:
        """Check if provider supports streaming responses."""
        return True

    def get_available_models(self) -> List[str]:
        """Get list of popular OpenRouter models.

        Note: OpenRouter supports 100+ models. This returns a curated list.
        Full list available at: https://openrouter.ai/models

        Returns:
            List of popular model identifiers
        """
        return [
            # Anthropic Claude
            "anthropic/claude-3-opus",
            "anthropic/claude-3-sonnet",
            "anthropic/claude-3-haiku",
            # OpenAI
            "openai/gpt-4-turbo",
            "openai/gpt-4",
            "openai/gpt-3.5-turbo",
            # Google
            "google/gemini-pro",
            "google/palm-2",
            # Meta Llama
            "meta-llama/llama-3-70b",
            "meta-llama/llama-2-70b",
            # Mistral
            "mistralai/mixtral-8x7b",
            "mistralai/mistral-7b",
            # Others
            "cohere/command",
            "perplexity/pplx-70b-online",
        ]

    def _handle_error(self, error: Exception) -> LLMResponse:
        """Handle OpenRouter API errors and convert to appropriate exceptions.

        Args:
            error: Exception from OpenRouter API

        Raises:
            LLMAuthenticationError: For auth errors
            LLMRateLimitError: For rate limit errors
            LLMAPIError: For other API errors
        """
        error_str = str(error).lower()

        if "authentication" in error_str or "api key" in error_str or "unauthorized" in error_str:
            raise LLMAuthenticationError(
                f"OpenRouter authentication failed: {error}. "
                f"Get API key at: https://openrouter.ai/keys"
            )
        elif "rate limit" in error_str or "quota" in error_str:
            raise LLMRateLimitError(f"OpenRouter rate limit exceeded: {error}")
        else:
            raise LLMAPIError(f"OpenRouter API error: {error}")
