"""Domain models for podx."""

from .episode import EpisodeMeta, AudioMeta
from .transcript import (
    Segment,
    Word,
    AlignedSegment,
    DiarizedSegment,
    Transcript,
)
from .analysis import (
    DeepcastQuote,
    DeepcastOutlineItem,
    DeepcastBrief,
)
from .pipeline import (
    PipelineConfig,
    PipelineResult,
)

__all__ = [
    # Episode models
    "EpisodeMeta",
    "AudioMeta",
    # Transcript models
    "Segment",
    "Word",
    "AlignedSegment",
    "DiarizedSegment",
    "Transcript",
    # Analysis models
    "DeepcastQuote",
    "DeepcastOutlineItem",
    "DeepcastBrief",
    # Pipeline models
    "PipelineConfig",
    "PipelineResult",
]
