"""Mock LLM provider for testing."""

from typing import Any, List, Optional

from .base import LLMMessage, LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing.

    Returns pre-configured responses and tracks all API calls
    for assertion in tests.

    Example:
        >>> mock = MockLLMProvider(responses=["Response 1", "Response 2"])
        >>> resp = mock.complete([LLMMessage.user("Hello")], model="test")
        >>> assert resp.content == "Response 1"
        >>> assert mock.call_count == 1
        >>> assert len(mock.calls) == 1
    """

    def __init__(self, responses: Optional[List[str]] = None):
        """Initialize mock provider.

        Args:
            responses: List of responses to return in order.
                      If None, returns empty string.
                      Cycles through if more calls than responses.
        """
        self.responses = responses or [""]
        self.call_count = 0
        self.calls: List[tuple[List[LLMMessage], str, float]] = []

    def complete(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Return next pre-configured response.

        Args:
            messages: List of conversation messages (recorded but not used)
            model: Model identifier (recorded but not used)
            temperature: Temperature (recorded but not used)
            max_tokens: Max tokens (recorded but not used)
            **kwargs: Additional parameters (ignored)

        Returns:
            LLMResponse with pre-configured content
        """
        # Record the call
        self.calls.append((messages, model, temperature))

        # Get response (cycle through if exhausted)
        response_idx = self.call_count % len(self.responses)
        content = self.responses[response_idx]

        self.call_count += 1

        return LLMResponse(
            content=content,
            model=model,
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )

    async def complete_async(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Async version of complete (just calls sync version).

        Args:
            messages: List of conversation messages
            model: Model identifier
            temperature: Temperature
            max_tokens: Max tokens
            **kwargs: Additional parameters

        Returns:
            LLMResponse with pre-configured content
        """
        return self.complete(messages, model, temperature, max_tokens, **kwargs)

    def supports_streaming(self) -> bool:
        """Mock provider doesn't support streaming."""
        return False

    def get_available_models(self) -> List[str]:
        """Return mock model list."""
        return ["mock-model-1", "mock-model-2"]

    def reset(self) -> None:
        """Reset call tracking.

        Useful when reusing mock provider across multiple tests.
        """
        self.call_count = 0
        self.calls = []

    def set_responses(self, responses: List[str]) -> None:
        """Update the list of responses.

        Args:
            responses: New list of responses
        """
        self.responses = responses
        self.reset()
