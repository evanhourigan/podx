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
__version__ = "2.0.0"

# Core processing engines
from podx.core.deepcast import DeepcastEngine
from podx.core.diarize import DiarizationEngine
from podx.core.export import ExportEngine
from podx.core.notion import NotionEngine
from podx.core.transcode import TranscodeEngine
from podx.core.transcribe import TranscriptionEngine
from podx.core.youtube import YouTubeEngine

# Main processing functions
from podx.core.fetch import fetch_episode, find_feed_url, search_podcasts
from podx.core.preprocess import (
    merge_segments,
    normalize_segments,
    normalize_text,
    preprocess_transcript,
)

# YouTube utilities
from podx.core.youtube import get_youtube_metadata, is_youtube_url

# Notion utilities
from podx.core.notion import md_to_blocks

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

# Error types from core modules
from podx.core.deepcast import DeepcastError
from podx.core.diarize import DiarizationError
from podx.core.export import ExportError
from podx.core.fetch import FetchError
from podx.core.notion import NotionError
from podx.core.preprocess import PreprocessError
from podx.core.transcode import TranscodeError
from podx.core.transcribe import TranscriptionError
from podx.core.youtube import YouTubeError

# General error types
from podx.errors import AIError, AudioError, NetworkError, PodxError, ValidationError

# Configuration
from podx.config import get_config

# Manifest system for episode tracking
from podx.manifest import (
    EpisodeManifest,
    Manifest,
    ManifestManager,
    PipelineSession,
    StageInfo,
)

__all__ = [
    # Version
    "__version__",
    # Core engines
    "DeepcastEngine",
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
    "AudioError",
    "DeepcastError",
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
    # Manifest
    "EpisodeManifest",
    "Manifest",
    "ManifestManager",
    "PipelineSession",
    "StageInfo",
]
