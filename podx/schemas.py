"""Backward compatibility layer for schemas.

This module provides backward compatibility by re-exporting models from the domain layer.
New code should import from podx.domain or podx.domain.models directly.
"""

# Re-export all models from domain for backward compatibility
from .domain.models import (
    AlignedSegment,
    AudioMeta,  # noqa: F401
    DeepcastBrief,
    DeepcastOutlineItem,
    DeepcastQuote,
    DiarizedSegment,
    EpisodeMeta,
    Segment,
    Transcript,
    Word,
)

__all__ = [
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
]
