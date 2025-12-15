"""Base classes for ASR provider Strategy pattern."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ProviderConfig:
    """Configuration for an ASR provider.

    This dataclass holds all configuration needed for transcription,
    avoiding primitive obsession and providing type safety.
    """

    model: str
    device: Optional[str] = None
    compute_type: Optional[str] = None
    language: str = "en"
    vad_filter: bool = True
    condition_on_previous_text: bool = True
    extra_options: Dict[str, Any] = field(default_factory=dict)
    progress_callback: Optional[Callable[[str], None]] = None

    def report_progress(self, message: str) -> None:
        """Report progress if callback is configured."""
        if self.progress_callback:
            self.progress_callback(message)


@dataclass
class TranscriptionResult:
    """Result of a transcription operation.

    Contains the transcript data plus metadata about how it was generated.
    """

    audio_path: str
    language: str
    asr_model: str
    asr_provider: str
    segments: List[Dict[str, Any]]
    text: str
    decoder_options: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "audio_path": self.audio_path,
            "language": self.language,
            "asr_model": self.asr_model,
            "asr_provider": self.asr_provider,
            "decoder_options": self.decoder_options or {},
            "segments": self.segments,
            "text": self.text,
        }


class ASRProvider(ABC):
    """Abstract base class for ASR (Automatic Speech Recognition) providers.

    This defines the Strategy interface. Each concrete provider (Local, OpenAI, HuggingFace)
    implements this interface, allowing them to be used interchangeably.

    Benefits of Strategy pattern:
    - Open/Closed: Can add new providers without modifying existing code
    - Single Responsibility: Each provider handles only one backend
    - Dependency Inversion: Code depends on abstraction, not concrete implementations
    - Testability: Easy to create mock providers for testing
    """

    def __init__(self, config: ProviderConfig):
        """Initialize provider with configuration.

        Args:
            config: Provider configuration
        """
        self.config = config

    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            TranscriptionResult with transcript data

        Raises:
            TranscriptionError: If transcription fails
            FileNotFoundError: If audio file doesn't exist
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get provider name (e.g., 'local', 'openai', 'hf')."""
        pass

    @property
    @abstractmethod
    def supported_models(self) -> List[str]:
        """Get list of supported model identifiers."""
        pass

    def normalize_model(self, model: str) -> str:
        """Normalize model identifier to provider-specific format.

        Override this in subclasses to implement model aliasing.

        Args:
            model: User-provided model identifier

        Returns:
            Normalized model identifier for this provider
        """
        return model

    def _report_progress(self, message: str) -> None:
        """Report progress via config callback."""
        self.config.report_progress(message)


class TranscriptionError(Exception):
    """Raised when transcription fails."""

    pass
