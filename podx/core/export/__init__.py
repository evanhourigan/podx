"""Export format providers using Strategy pattern.

This module implements the Strategy pattern for transcript export formats,
enabling easy addition of new formats without modifying existing code.

Usage:
    from podx.core.export import get_formatter, TXTFormatter, SRTFormatter

    formatter = get_formatter("srt")
    content = formatter.format(segments)
"""

# Import legacy classes and functions for backward compatibility
from ..export_legacy import (
    ExportEngine,
    ExportError,
    export_transcript,
    format_timestamp,
    write_if_changed,
)
from .base import ExportFormatter, FormatRegistry
from .formats import MDFormatter, SRTFormatter, TXTFormatter, VTTFormatter
from .html_formatter import HTMLFormatter
from .pdf_formatter import PDFFormatter

__all__ = [
    # Legacy (backward compatibility)
    "ExportEngine",
    "ExportError",
    "export_transcript",
    "format_timestamp",
    "write_if_changed",
    # Base
    "ExportFormatter",
    "FormatRegistry",
    # Formats
    "TXTFormatter",
    "SRTFormatter",
    "VTTFormatter",
    "MDFormatter",
    "PDFFormatter",
    "HTMLFormatter",
]
