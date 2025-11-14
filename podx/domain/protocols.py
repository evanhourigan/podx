"""Protocol definitions for core PodX services.

These protocols define the interfaces for major subsystems, enabling:
- Dependency injection and inversion of control
- Easy testing with mock implementations
- Plugin architecture for extending functionality
- Clear contracts for service integration
"""

from pathlib import Path
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from .enums import AnalysisType, ASRProvider
from .models.analysis import DeepcastBrief
from .models.transcript import Transcript


# ============================================================================
# Result Types for Better Error Handling
# ============================================================================


class Result:
    """Base result type for operations that can succeed or fail."""

    def __init__(self, success: bool, data: Any = None, error: Optional[str] = None):
        self._success = success
        self._data = data
        self._error = error

    @property
    def success(self) -> bool:
        """Whether the operation succeeded."""
        return self._success

    @property
    def data(self) -> Any:
        """The result data (only valid if success=True)."""
        if not self._success:
            raise ValueError(f"Cannot access data on failed result: {self._error}")
        return self._data

    @property
    def error(self) -> Optional[str]:
        """The error message (only valid if success=False)."""
        return self._error

    @classmethod
    def ok(cls, data: Any = None) -> "Result":
        """Create a successful result."""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "Result":
        """Create a failed result."""
        return cls(success=False, error=error)


class TranscriptResult(Result):
    """Result of a transcription operation."""

    @property
    def transcript(self) -> Transcript:
        """Get the transcript (only valid if success=True)."""
        return self.data


class AnalysisResult(Result):
    """Result of an analysis operation."""

    @property
    def analysis(self) -> DeepcastBrief:
        """Get the analysis (only valid if success=True)."""
        return self.data


class PublishResult(Result):
    """Result of a publish operation."""

    @property
    def url(self) -> Optional[str]:
        """Get the published URL (only valid if success=True)."""
        return self.data.get("url") if isinstance(self.data, dict) else None


class FetchResult(Result):
    """Result of a fetch operation."""

    @property
    def episode_metadata(self) -> Dict[str, Any]:
        """Get the episode metadata (only valid if success=True)."""
        return self.data


# ============================================================================
# Core Service Protocols
# ============================================================================


@runtime_checkable
class Fetcher(Protocol):
    """Protocol for podcast episode fetching services.

    Implementations handle discovering and downloading podcast episodes
    from various sources (RSS feeds, YouTube, etc.).
    """

    def fetch_episode(
        self,
        show_name: Optional[str] = None,
        rss_url: Optional[str] = None,
        date: Optional[str] = None,
        title_contains: Optional[str] = None,
        youtube_url: Optional[str] = None,
        interactive: bool = False,
    ) -> FetchResult:
        """Fetch a podcast episode.

        Args:
            show_name: Name of the show to search for
            rss_url: Direct RSS feed URL
            date: Episode date to match (YYYY-MM-DD)
            title_contains: Text that should appear in episode title
            youtube_url: YouTube video URL
            interactive: Whether to show interactive selection UI

        Returns:
            FetchResult containing episode metadata or error

        Raises:
            NotImplementedError: If not implemented by concrete class
        """
        ...


@runtime_checkable
class Transcriber(Protocol):
    """Protocol for audio transcription services.

    Implementations handle converting audio files to text transcripts
    using various ASR (Automatic Speech Recognition) backends.
    """

    def transcribe(
        self,
        audio_path: Path,
        model: str,
        language: str = "en",
        provider: Optional[ASRProvider] = None,
        **kwargs: Any,
    ) -> TranscriptResult:
        """Transcribe an audio file.

        Args:
            audio_path: Path to the audio file
            model: Name of the ASR model to use
            language: Language code (e.g., "en", "es", "fr")
            provider: ASR provider (local, openai, hf)
            **kwargs: Additional provider-specific options

        Returns:
            TranscriptResult containing transcript or error

        Raises:
            NotImplementedError: If not implemented by concrete class
        """
        ...


@runtime_checkable
class Diarizer(Protocol):
    """Protocol for speaker diarization services.

    Implementations handle identifying and labeling different speakers
    in audio/transcript content.
    """

    def diarize(
        self,
        audio_path: Path,
        transcript: Transcript,
        language: str = "en",
        **kwargs: Any,
    ) -> TranscriptResult:
        """Add speaker identification to a transcript.

        Args:
            audio_path: Path to the audio file
            transcript: Existing transcript to enhance
            language: Language code for alignment models
            **kwargs: Additional diarization options

        Returns:
            TranscriptResult with speaker labels or error

        Raises:
            NotImplementedError: If not implemented by concrete class
        """
        ...


@runtime_checkable
class Analyzer(Protocol):
    """Protocol for transcript analysis services.

    Implementations handle AI-powered analysis of transcripts to generate
    summaries, key points, quotes, and other insights.
    """

    def analyze(
        self,
        transcript: Transcript,
        model: str,
        analysis_type: Optional[AnalysisType] = None,
        custom_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AnalysisResult:
        """Analyze a transcript using AI.

        Args:
            transcript: The transcript to analyze
            model: AI model to use for analysis
            analysis_type: Type of analysis (interview, panel, solo, etc.)
            custom_prompt: Custom analysis prompt
            **kwargs: Additional analysis options

        Returns:
            AnalysisResult containing analysis or error

        Raises:
            NotImplementedError: If not implemented by concrete class
        """
        ...


@runtime_checkable
class Publisher(Protocol):
    """Protocol for content publishing services.

    Implementations handle publishing processed content to various
    destinations (Notion, blogs, etc.).
    """

    def publish(
        self,
        content: str,
        metadata: Dict[str, Any],
        destination: str,
        **kwargs: Any,
    ) -> PublishResult:
        """Publish content to a destination.

        Args:
            content: The content to publish (markdown, JSON, etc.)
            metadata: Episode and analysis metadata
            destination: Where to publish (database ID, URL, etc.)
            **kwargs: Additional publishing options

        Returns:
            PublishResult containing published URL or error

        Raises:
            NotImplementedError: If not implemented by concrete class
        """
        ...


@runtime_checkable
class Exporter(Protocol):
    """Protocol for transcript export services.

    Implementations handle converting transcripts to various output
    formats (TXT, SRT, VTT, MD, etc.).
    """

    def export(
        self,
        transcript: Transcript,
        output_path: Path,
        format: str,
        **kwargs: Any,
    ) -> Result:
        """Export transcript to a specific format.

        Args:
            transcript: The transcript to export
            output_path: Where to save the export
            format: Output format (txt, srt, vtt, md, etc.)
            **kwargs: Format-specific options

        Returns:
            Result indicating success or error

        Raises:
            NotImplementedError: If not implemented by concrete class
        """
        ...


@runtime_checkable
class Preprocessor(Protocol):
    """Protocol for transcript preprocessing services.

    Implementations handle cleaning, normalizing, and enhancing
    raw transcripts before further processing.
    """

    def preprocess(
        self,
        transcript: Transcript,
        merge: bool = True,
        normalize: bool = True,
        restore_punctuation: bool = False,
        **kwargs: Any,
    ) -> TranscriptResult:
        """Preprocess a transcript.

        Args:
            transcript: The transcript to preprocess
            merge: Whether to merge short segments
            normalize: Whether to normalize text
            restore_punctuation: Whether to restore punctuation
            **kwargs: Additional preprocessing options

        Returns:
            TranscriptResult with preprocessed transcript or error

        Raises:
            NotImplementedError: If not implemented by concrete class
        """
        ...


# ============================================================================
# Progress and Logging Protocols
# ============================================================================


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for progress reporting during long operations."""

    def report(self, message: str, progress: Optional[float] = None) -> None:
        """Report progress.

        Args:
            message: Progress message to display
            progress: Optional progress percentage (0.0 to 1.0)

        Raises:
            NotImplementedError: If not implemented by concrete class
        """
        ...


@runtime_checkable
class Logger(Protocol):
    """Protocol for logging operations."""

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        ...

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        ...

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        ...

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        ...
