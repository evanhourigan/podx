"""Concrete export format implementations."""

from typing import Any, Dict, List

from .base import ExportFormatter, FormatRegistry
from .html_formatter import HTMLFormatter
from .pdf_formatter import PDFFormatter


def format_timestamp(sec: float) -> str:
    """Format seconds as SRT/VTT timestamp (HH:MM:SS,mmm or HH:MM:SS.mmm)."""
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec) % 60
    m = (int(sec) // 60) % 60
    h = int(sec) // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


class TXTFormatter(ExportFormatter):
    """Plain text formatter.

    Outputs transcript as simple newline-separated text.
    """

    @property
    def extension(self) -> str:
        return "txt"

    @property
    def name(self) -> str:
        return "Plain Text"

    def format(self, segments: List[Dict[str, Any]]) -> str:
        """Convert segments to plain text."""
        lines = [s["text"].strip() for s in segments]
        return "\n".join(lines) + "\n"


class SRTFormatter(ExportFormatter):
    """SubRip subtitle formatter.

    Outputs transcript in SRT subtitle format with timestamps.
    """

    @property
    def extension(self) -> str:
        return "srt"

    @property
    def name(self) -> str:
        return "SubRip Subtitles"

    def format(self, segments: List[Dict[str, Any]]) -> str:
        """Convert segments to SRT subtitle format."""
        lines = []
        for i, s in enumerate(segments, 1):
            speaker = s.get("speaker")
            text = s["text"].strip()
            if speaker:
                text = f"[{speaker}] {text}"

            lines.append(str(i))
            lines.append(f"{format_timestamp(s['start'])} --> {format_timestamp(s['end'])}")
            lines.append(text)
            lines.append("")  # Blank line between entries

        return "\n".join(lines)


class VTTFormatter(ExportFormatter):
    """WebVTT subtitle formatter.

    Outputs transcript in VTT subtitle format with timestamps.
    Similar to SRT but uses dots instead of commas for milliseconds.
    """

    @property
    def extension(self) -> str:
        return "vtt"

    @property
    def name(self) -> str:
        return "WebVTT Subtitles"

    def format(self, segments: List[Dict[str, Any]]) -> str:
        """Convert segments to VTT subtitle format."""
        lines = ["WEBVTT", ""]  # VTT header

        for i, s in enumerate(segments, 1):
            speaker = s.get("speaker")
            text = s["text"].strip()
            if speaker:
                text = f"[{speaker}] {text}"

            ts = format_timestamp(s["start"]).replace(",", ".")
            te = format_timestamp(s["end"]).replace(",", ".")

            lines.append(str(i))
            lines.append(f"{ts} --> {te}")
            lines.append(text)
            lines.append("")  # Blank line between entries

        return "\n".join(lines)


class MDFormatter(ExportFormatter):
    """Markdown formatter.

    Outputs transcript as markdown with timestamps and speaker labels.
    """

    @property
    def extension(self) -> str:
        return "md"

    @property
    def name(self) -> str:
        return "Markdown"

    def format(self, segments: List[Dict[str, Any]]) -> str:
        """Convert segments to Markdown format."""
        lines = ["# Transcript", ""]

        for s in segments:
            speaker = s.get("speaker", "Unknown")
            start_ts = format_timestamp(s["start"])
            text = s["text"].strip()

            lines.append(f"**[{start_ts}] {speaker}:** {text}")
            lines.append("")

        return "\n".join(lines)


# Register all formats in the registry
FormatRegistry.register("txt", TXTFormatter)
FormatRegistry.register("srt", SRTFormatter)
FormatRegistry.register("vtt", VTTFormatter)
FormatRegistry.register("md", MDFormatter)
FormatRegistry.register("pdf", PDFFormatter)
FormatRegistry.register("html", HTMLFormatter)
