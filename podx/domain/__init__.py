"""Domain layer for podx - data models, enums, protocols, and business logic."""

from .enums import AnalysisType, ASRPreset, ASRProvider, AudioFormat, PipelineStep
from .models import (
    AlignedSegment,
    AudioMeta,
    DeepcastBrief,
    DeepcastOutlineItem,
    DeepcastQuote,
    DiarizedSegment,
    EpisodeMeta,
    PipelineConfig,
    PipelineResult,
    Segment,
    Transcript,
    Word,
)
from .protocols import (
    Analyzer,
    AnalysisResult,
    Diarizer,
    Exporter,
    Fetcher,
    FetchResult,
    Logger,
    Preprocessor,
    ProgressReporter,
    Publisher,
    PublishResult,
    Result,
    Transcriber,
    TranscriptResult,
)

__all__ = [
    # Enums
    "PipelineStep",
    "AnalysisType",
    "ASRProvider",
    "ASRPreset",
    "AudioFormat",
    # Models
    "EpisodeMeta",
    "AudioMeta",
    "Segment",
    "Word",
    "AlignedSegment",
    "DiarizedSegment",
    "Transcript",
    "DeepcastQuote",
    "DeepcastOutlineItem",
    "DeepcastBrief",
    "PipelineConfig",
    "PipelineResult",
    # Protocols
    "Fetcher",
    "Transcriber",
    "Diarizer",
    "Analyzer",
    "Publisher",
    "Exporter",
    "Preprocessor",
    "ProgressReporter",
    "Logger",
    # Result Types
    "Result",
    "TranscriptResult",
    "AnalysisResult",
    "PublishResult",
    "FetchResult",
]
