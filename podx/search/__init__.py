"""Transcript search and analysis module.

Provides full-text search, semantic search, and quote extraction
for podcast transcripts.
"""

from podx.search.database import TranscriptDatabase
from podx.search.quotes import QuoteExtractor

try:
    from podx.search.semantic import SemanticSearch

    __all__ = [
        "TranscriptDatabase",
        "QuoteExtractor",
        "SemanticSearch",
    ]
except ImportError:
    # Semantic search requires optional dependencies
    __all__ = [
        "TranscriptDatabase",
        "QuoteExtractor",
    ]
