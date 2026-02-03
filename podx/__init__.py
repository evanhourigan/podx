"""PodX Python SDK.

A composable podcast processing pipeline providing clean Python APIs for:
- Podcast episode fetching and metadata extraction
- Audio transcoding and format conversion
- Speech-to-text transcription (Whisper, OpenAI, HuggingFace)
- Speaker diarization with WhisperX
- AI-powered content analysis and summarization
- Export to multiple formats (TXT, SRT, VTT, MD)
- Notion integration

Quick Start:
    >>> from podx import TranscriptionEngine
    >>> engine = TranscriptionEngine(model="base")
    >>> transcript = engine.transcribe("audio.wav")
    >>> print(f"Transcribed {len(transcript['segments'])} segments")

For complete examples, see: https://github.com/evanhourigan/podx
"""

# Version
__version__ = "4.3.0"

# Configuration
from podx.config import get_config

# Core processing engines
from podx.core.analyze import AnalyzeEngine, AnalyzeError
from podx.core.diarize import DiarizationEngine, DiarizationError
from podx.core.export import ExportEngine, ExportError
from podx.core.fetch import FetchError, fetch_episode, find_feed_url, search_podcasts
from podx.core.notion import NotionEngine, NotionError, md_to_blocks
from podx.core.preprocess import (
    PreprocessError,
    merge_segments,
    normalize_segments,
    normalize_text,
    preprocess_transcript,
)
from podx.core.transcode import TranscodeEngine, TranscodeError
from podx.core.transcribe import TranscriptionEngine, TranscriptionError
from podx.core.youtube import YouTubeEngine, YouTubeError, get_youtube_metadata, is_youtube_url

# General error types
from podx.errors import AIError, AudioError, NetworkError, PodxError, ValidationError

# Common schemas and types
from podx.schemas import (
    AlignedSegment,
    AudioMeta,
    DeepcastBrief,
    DeepcastOutlineItem,
    DeepcastQuote,
    DiarizedSegment,
    EpisodeMeta,
    Segment,
    Transcript,
    Word,
)

# Backwards compatibility aliases
DeepcastEngine = AnalyzeEngine
DeepcastError = AnalyzeError

__all__ = [
    # Version
    "__version__",
    # Core engines
    "AnalyzeEngine",
    "DeepcastEngine",  # Backwards compatibility alias for AnalyzeEngine
    "DiarizationEngine",
    "ExportEngine",
    "NotionEngine",
    "TranscodeEngine",
    "TranscriptionEngine",
    "YouTubeEngine",
    # Processing functions
    "fetch_episode",
    "find_feed_url",
    "search_podcasts",
    "merge_segments",
    "normalize_segments",
    "normalize_text",
    "preprocess_transcript",
    "get_youtube_metadata",
    "is_youtube_url",
    "md_to_blocks",
    # Schemas
    "AlignedSegment",
    "AudioMeta",
    "DeepcastBrief",
    "DeepcastOutlineItem",
    "DeepcastQuote",
    "DiarizedSegment",
    "EpisodeMeta",
    "Segment",
    "Transcript",
    "Word",
    # Errors
    "AIError",
    "AnalyzeError",
    "AudioError",
    "DeepcastError",  # Backwards compatibility alias for AnalyzeError
    "DiarizationError",
    "ExportError",
    "FetchError",
    "NetworkError",
    "NotionError",
    "PodxError",
    "PreprocessError",
    "TranscodeError",
    "TranscriptionError",
    "ValidationError",
    "YouTubeError",
    # Config
    "get_config",
]
