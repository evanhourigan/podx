"""Batch processing for multiple episodes.

This module provides batch processing capabilities for processing multiple
episodes in parallel with auto-discovery, filtering, and error handling.
"""

from .discovery import EpisodeDiscovery, EpisodeFilter
from .processor import BatchProcessor, BatchResult
from .status import BatchStatus, ProcessingState

__all__ = [
    "EpisodeDiscovery",
    "EpisodeFilter",
    "BatchProcessor",
    "BatchResult",
    "BatchStatus",
    "ProcessingState",
]
