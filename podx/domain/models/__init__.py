"""Domain models for podx."""

from .analysis import DeepcastBrief, DeepcastOutlineItem, DeepcastQuote
from .episode import AudioMeta, EpisodeMeta
from .pipeline import PipelineConfig, PipelineResult
from .transcript import (AlignedSegment, DiarizedSegment, Segment, Transcript,
                         Word)

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
