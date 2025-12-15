"""Base classes and interfaces for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LLMMessage:
    """A single message in an LLM conversation.

    Attributes:
        role: Message role (system, user, assistant)
        content: Message content/text
    """

    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary format for API calls."""
        return {"role": self.role, "content": self.content}

    @classmethod
    def system(cls, content: str) -> "LLMMessage":
        """Create a system message."""
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "LLMMessage":
        """Create a user message."""
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> "LLMMessage":
        """Create an assistant message."""
        return cls(role="assistant", content=content)


@dataclass
class LLMResponse:
    """Response from an LLM provider.

    Attributes:
        content: Generated text content
        model: Model that generated the response
        usage: Token usage information (if available)
        raw_response: Raw provider-specific response object
    """

    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    raw_response: Optional[Any] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM providers must implement this interface to ensure
    consistent behavior across different backends.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize provider.

        Args:
            api_key: API key for authentication
            base_url: Optional base URL override
            **kwargs: Provider-specific arguments
        """
        # Concrete implementations handle these
        pass

    @abstractmethod
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
            model: Model identifier (provider-specific)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific additional parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMProviderError: If API call fails
        """
        pass

    @abstractmethod
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
            model: Model identifier (provider-specific)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific additional parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMProviderError: If API call fails
        """
        pass

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Check if provider supports streaming responses.

        Returns:
            True if streaming is supported
        """
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Get list of available models for this provider.

        Returns:
            List of model identifiers
        """
        pass


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""

    pass


class LLMAuthenticationError(LLMProviderError):
    """Raised when API authentication fails."""

    pass


class LLMRateLimitError(LLMProviderError):
    """Raised when rate limit is exceeded."""

    pass


class LLMAPIError(LLMProviderError):
    """Raised when API returns an error."""

    pass
