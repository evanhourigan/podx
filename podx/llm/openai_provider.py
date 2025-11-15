"""OpenAI LLM provider implementation."""

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


class OpenAIProvider(LLMProvider):
    """OpenAI API provider for GPT models.

    Supports GPT-4, GPT-3.5, and other OpenAI models.
    Uses the official OpenAI Python library.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            base_url: Optional base URL override (for Azure, etc.)
            organization: Optional organization ID

        Raises:
            LLMProviderError: If openai library not installed or API key missing
        """
        try:
            from openai import AsyncOpenAI, OpenAI
        except ImportError:
            raise LLMProviderError(
                "openai library not installed. Install with: pip install openai"
            )

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self.organization = organization

        if not self.api_key:
            raise LLMAuthenticationError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Initialize both sync and async clients
        self._sync_client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            organization=self.organization,
        )
        self._async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            organization=self.organization,
        )

        logger.debug("Initialized OpenAI provider")

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
            model: OpenAI model (e.g., 'gpt-4', 'gpt-3.5-turbo')
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenAI API parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMAuthenticationError: If API key is invalid
            LLMRateLimitError: If rate limit exceeded
            LLMAPIError: If API returns an error
        """
        try:
            response = self._sync_client.chat.completions.create(
                model=model,
                messages=[msg.to_dict() for msg in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
                if response.usage
                else None,
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
            model: OpenAI model (e.g., 'gpt-4', 'gpt-3.5-turbo')
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenAI API parameters

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
                messages=[msg.to_dict() for msg in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
                if response.usage
                else None,
                raw_response=response,
            )

        except Exception as e:
            return self._handle_error(e)

    def supports_streaming(self) -> bool:
        """Check if provider supports streaming responses."""
        return True

    def get_available_models(self) -> List[str]:
        """Get list of available OpenAI models.

        Returns:
            List of model identifiers
        """
        return [
            "gpt-4-turbo",
            "gpt-4",
            "gpt-4-32k",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "gpt-4o",
            "gpt-4o-mini",
        ]

    def _handle_error(self, error: Exception) -> LLMResponse:
        """Handle OpenAI API errors and convert to appropriate exceptions.

        Args:
            error: Exception from OpenAI API

        Raises:
            LLMAuthenticationError: For auth errors
            LLMRateLimitError: For rate limit errors
            LLMAPIError: For other API errors
        """
        error_str = str(error).lower()

        if "authentication" in error_str or "api key" in error_str:
            raise LLMAuthenticationError(f"OpenAI authentication failed: {error}")
        elif "rate limit" in error_str or "quota" in error_str:
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {error}")
        else:
            raise LLMAPIError(f"OpenAI API error: {error}")
