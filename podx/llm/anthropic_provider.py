"""Anthropic LLM provider implementation."""

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


class AnthropicProvider(LLMProvider):
    """Anthropic API provider for Claude models.

    Supports Claude 3 (Opus, Sonnet, Haiku) and Claude 2.x models.
    Uses the official Anthropic Python library.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            base_url: Optional base URL override

        Raises:
            LLMProviderError: If anthropic library not installed or API key missing
        """
        try:
            from anthropic import Anthropic, AsyncAnthropic
        except ImportError:
            raise LLMProviderError(
                "anthropic library not installed. Install with: pip install anthropic"
            )

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = base_url

        if not self.api_key:
            raise LLMAuthenticationError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Initialize both sync and async clients
        if self.base_url:
            self._sync_client = Anthropic(api_key=self.api_key, base_url=self.base_url)
            self._async_client = AsyncAnthropic(api_key=self.api_key, base_url=self.base_url)
        else:
            self._sync_client = Anthropic(api_key=self.api_key)
            self._async_client = AsyncAnthropic(api_key=self.api_key)

        logger.debug("Initialized Anthropic provider")

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
            model: Claude model (e.g., 'claude-3-opus-20240229')
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate (required for Claude)
            **kwargs: Additional Anthropic API parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMAuthenticationError: If API key is invalid
            LLMRateLimitError: If rate limit exceeded
            LLMAPIError: If API returns an error
        """
        # Extract system message if present
        system_message = None
        chat_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                chat_messages.append(msg.to_dict())

        # Claude requires max_tokens — 16384 allows full analysis + JSON output
        if max_tokens is None:
            max_tokens = 16384

        try:
            create_kwargs = {
                "model": model,
                "messages": chat_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            }

            if system_message:
                create_kwargs["system"] = system_message

            response = self._sync_client.messages.create(**create_kwargs)

            # Extract text content from response
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            return LLMResponse(
                content=content,
                model=response.model,
                usage=(
                    {
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
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
            model: Claude model (e.g., 'claude-3-opus-20240229')
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate (required for Claude)
            **kwargs: Additional Anthropic API parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMAuthenticationError: If API key is invalid
            LLMRateLimitError: If rate limit exceeded
            LLMAPIError: If API returns an error
        """
        # Extract system message if present
        system_message = None
        chat_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                chat_messages.append(msg.to_dict())

        # Claude requires max_tokens — 16384 allows full analysis + JSON output
        if max_tokens is None:
            max_tokens = 16384

        try:
            create_kwargs = {
                "model": model,
                "messages": chat_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            }

            if system_message:
                create_kwargs["system"] = system_message

            response = await self._async_client.messages.create(**create_kwargs)

            # Extract text content from response
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            return LLMResponse(
                content=content,
                model=response.model,
                usage=(
                    {
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
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
        """Get list of available Claude models.

        Returns:
            List of model identifiers
        """
        return [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0",
        ]

    def _handle_error(self, error: Exception) -> LLMResponse:
        """Handle Anthropic API errors and convert to appropriate exceptions.

        Args:
            error: Exception from Anthropic API

        Raises:
            LLMAuthenticationError: For auth errors
            LLMRateLimitError: For rate limit errors
            LLMAPIError: For other API errors
        """
        error_str = str(error).lower()

        if "authentication" in error_str or "api key" in error_str:
            raise LLMAuthenticationError(f"Anthropic authentication failed: {error}")
        elif "rate limit" in error_str or "overloaded" in error_str:
            raise LLMRateLimitError(f"Anthropic rate limit exceeded: {error}")
        else:
            raise LLMAPIError(f"Anthropic API error: {error}")
