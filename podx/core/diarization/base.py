"""Base classes for diarization provider Strategy pattern.

Mirrors the ASR provider architecture in transcription/base.py.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class DiarizationConfig:
    """Configuration for a diarization provider.

    This dataclass holds all configuration needed for diarization,
    providing type safety and avoiding primitive obsession.
    """

    language: str = "en"
    device: Optional[str] = None
    hf_token: Optional[str] = None
    num_speakers: Optional[int] = None
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None
    progress_callback: Optional[Callable[[str], None]] = None
    extra_options: Dict[str, Any] = field(default_factory=dict)

    def report_progress(self, message: str) -> None:
        """Report progress if callback is configured."""
        if self.progress_callback:
            self.progress_callback(message)


@dataclass
class DiarizationResult:
    """Result of a diarization operation.

    Contains the diarized transcript data plus metadata about how it was generated.
    """

    audio_path: str
    segments: List[Dict[str, Any]]
    provider: str
    speakers_count: int
    language: str
    chunked: bool = False
    chunk_info: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format compatible with transcript.json."""
        return {
            "segments": self.segments,
            "diarized": True,
            "diarization_provider": self.provider,
            "speakers_count": self.speakers_count,
        }


class DiarizationProvider(ABC):
    """Abstract base class for diarization providers.

    This defines the Strategy interface. Each concrete provider (Local, RunPod)
    implements this interface, allowing them to be used interchangeably.

    Benefits of Strategy pattern:
    - Open/Closed: Can add new providers without modifying existing code
    - Single Responsibility: Each provider handles only one backend
    - Dependency Inversion: Code depends on abstraction, not concrete implementations
    - Testability: Easy to create mock providers for testing
    """

    def __init__(self, config: DiarizationConfig):
        """Initialize provider with configuration.

        Args:
            config: Provider configuration
        """
        self.config = config

    @abstractmethod
    def diarize(
        self,
        audio_path: Path,
        transcript_segments: List[Dict[str, Any]],
    ) -> DiarizationResult:
        """Diarize audio with speaker identification.

        Args:
            audio_path: Path to audio file
            transcript_segments: List of transcript segments with text and timing

        Returns:
            DiarizationResult with speaker-labeled segments

        Raises:
            DiarizationError: If diarization fails
            FileNotFoundError: If audio file doesn't exist
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get provider name (e.g., 'local', 'runpod')."""
        pass

    def _report_progress(self, message: str) -> None:
        """Report progress via config callback."""
        self.config.report_progress(message)


class DiarizationProviderError(Exception):
    """Raised when a diarization provider fails."""

    pass
