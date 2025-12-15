"""Ollama LLM provider implementation.

Ollama enables running LLMs locally (Llama 2, Mistral, Code Llama, etc.)
Provides privacy and no API costs, but requires local GPU/CPU resources.
"""

import os
from typing import Any, List, Optional

from ..logging import get_logger
from .base import LLMAPIError, LLMMessage, LLMProvider, LLMProviderError, LLMResponse

logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama provider for local LLM inference.

    Ollama runs models locally, providing:
    - Privacy (no data sent to cloud)
    - No API costs
    - Offline operation
    - Fast inference with GPU

    Requires Ollama installed: https://ollama.ai
    """

    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(
        self,
        api_key: Optional[str] = None,  # Not used, but kept for interface compatibility
        base_url: Optional[str] = None,
    ):
        """Initialize Ollama provider.

        Args:
            api_key: Not used (Ollama doesn't require auth), kept for compatibility
            base_url: Ollama server URL (defaults to http://localhost:11434)

        Raises:
            LLMProviderError: If ollama library not installed
        """
        try:
            from ollama import AsyncClient, Client
        except ImportError:
            raise LLMProviderError("ollama library not installed. Install with: pip install ollama")

        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", self.DEFAULT_BASE_URL)

        # Initialize both sync and async clients
        self._sync_client = Client(host=self.base_url)
        self._async_client = AsyncClient(host=self.base_url)

        logger.debug(f"Initialized Ollama provider (base_url={self.base_url})")

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
            model: Ollama model name (e.g., 'llama2', 'mistral', 'codellama')
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate (called num_predict in Ollama)
            **kwargs: Additional Ollama parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMAPIError: If Ollama API returns an error

        Note:
            Models must be pulled first: `ollama pull llama2`
            Available models: llama2, mistral, codellama, vicuna, etc.
        """
        try:
            # Convert messages to Ollama format
            ollama_messages = [msg.to_dict() for msg in messages]

            # Build options dict for Ollama
            options = {"temperature": temperature}
            if max_tokens:
                options["num_predict"] = max_tokens

            response = self._sync_client.chat(
                model=model,
                messages=ollama_messages,
                options=options,
                **kwargs,
            )

            # Extract content from response
            content = response.get("message", {}).get("content", "")

            # Ollama doesn't always provide token counts, estimate if missing
            usage = None
            if "prompt_eval_count" in response or "eval_count" in response:
                prompt_tokens = response.get("prompt_eval_count", 0)
                completion_tokens = response.get("eval_count", 0)
                usage = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                }

            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
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
            model: Ollama model name (e.g., 'llama2', 'mistral')
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional Ollama parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMAPIError: If Ollama API returns an error
        """
        try:
            # Convert messages to Ollama format
            ollama_messages = [msg.to_dict() for msg in messages]

            # Build options dict for Ollama
            options = {"temperature": temperature}
            if max_tokens:
                options["num_predict"] = max_tokens

            response = await self._async_client.chat(
                model=model,
                messages=ollama_messages,
                options=options,
                **kwargs,
            )

            # Extract content from response
            content = response.get("message", {}).get("content", "")

            # Ollama doesn't always provide token counts, estimate if missing
            usage = None
            if "prompt_eval_count" in response or "eval_count" in response:
                prompt_tokens = response.get("prompt_eval_count", 0)
                completion_tokens = response.get("eval_count", 0)
                usage = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                }

            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                raw_response=response,
            )

        except Exception as e:
            return self._handle_error(e)

    def supports_streaming(self) -> bool:
        """Check if provider supports streaming responses."""
        return True

    def get_available_models(self) -> List[str]:
        """Get list of locally available Ollama models.

        Returns:
            List of model names pulled on this machine

        Note:
            This queries the local Ollama instance.
            Returns empty list if Ollama is not running.
        """
        try:
            response = self._sync_client.list()
            models = response.get("models", [])
            return [model.get("name", "") for model in models if model.get("name")]
        except Exception as e:
            logger.warning(f"Failed to list Ollama models: {e}")
            # Return common model names as fallback
            return [
                "llama2",
                "llama2:13b",
                "llama2:70b",
                "mistral",
                "mixtral",
                "codellama",
                "vicuna",
            ]

    def _handle_error(self, error: Exception) -> LLMResponse:
        """Handle Ollama API errors and convert to appropriate exceptions.

        Args:
            error: Exception from Ollama API

        Raises:
            LLMAPIError: For API errors
        """
        error_str = str(error).lower()

        if "connection" in error_str or "refused" in error_str:
            raise LLMAPIError(
                f"Failed to connect to Ollama. Is Ollama running? "
                f"Start with: ollama serve\nError: {error}"
            )
        elif "not found" in error_str or "no such" in error_str:
            raise LLMAPIError(
                f"Model not found. Pull it first with: ollama pull <model>\nError: {error}"
            )
        else:
            raise LLMAPIError(f"Ollama API error: {error}")
