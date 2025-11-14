"""Export format providers using Strategy pattern.

This module implements the Strategy pattern for transcript export formats,
enabling easy addition of new formats without modifying existing code.

Usage:
    from podx.core.export import get_formatter, TXTFormatter, SRTFormatter

    formatter = get_formatter("srt")
    content = formatter.format(segments)
"""

# Import legacy classes for backward compatibility
from ..export_legacy import ExportEngine, ExportError
from .base import ExportFormatter, FormatRegistry
from .formats import MDFormatter, SRTFormatter, TXTFormatter, VTTFormatter

__all__ = [
    # Legacy (backward compatibility)
    "ExportEngine",
    "ExportError",
    # Base
    "ExportFormatter",
    "FormatRegistry",
    # Formats
    "TXTFormatter",
    "SRTFormatter",
    "VTTFormatter",
    "MDFormatter",
]
