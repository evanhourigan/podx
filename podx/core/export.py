"""Core export engine - pure business logic.

No UI dependencies, no CLI concerns. Just transcript format conversion.
Handles conversion to TXT, SRT, VTT, and Markdown formats.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class ExportError(Exception):
    """Raised when export operations fail."""

    pass


def format_timestamp(sec: float) -> str:
    """Format seconds as SRT/VTT timestamp (HH:MM:SS,mmm or HH:MM:SS.mmm)."""
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec) % 60
    m = (int(sec) // 60) % 60
    h = int(sec) // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_if_changed(path: Path, content: str, replace: bool = False) -> bool:
    """Write content to file only if it has changed (when replace=True).

    Args:
        path: Path to write to
        content: Content to write
        replace: If True, only write if content differs from existing

    Returns:
        True if file was written, False if skipped
    """
    if replace and path.exists():
        existing_content = path.read_text(encoding="utf-8")
        if existing_content == content:
            return False  # Content unchanged, skip write

    path.write_text(content, encoding="utf-8")
    return True


class ExportEngine:
    """Pure export logic with no UI dependencies.

    Handles conversion of transcript JSON to various text formats:
    - TXT: Plain text
    - SRT: SubRip subtitles
    - VTT: WebVTT subtitles
    - MD: Markdown

    Can be used by CLI, TUI studio, web API, or any other interface.
    """

    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """Initialize export engine.

        Args:
            progress_callback: Optional callback for progress updates
        """
        self.progress_callback = progress_callback

    def _report_progress(self, message: str):
        """Report progress via callback if available."""
        if self.progress_callback:
            self.progress_callback(message)

    def to_txt(self, segments: List[Dict[str, Any]]) -> str:
        """Convert segments to plain text format.

        Args:
            segments: List of transcript segments

        Returns:
            Plain text string
        """
        lines = [s["text"].strip() for s in segments]
        return "\n".join(lines) + "\n"

    def to_srt(self, segments: List[Dict[str, Any]]) -> str:
        """Convert segments to SRT subtitle format.

        Args:
            segments: List of transcript segments with start/end times

        Returns:
            SRT formatted string
        """
        lines = []
        for i, s in enumerate(segments, 1):
            speaker = s.get("speaker")
            text = s["text"].strip()
            if speaker:
                text = f"[{speaker}] {text}"

            lines.append(str(i))
            lines.append(
                f"{format_timestamp(s['start'])} --> {format_timestamp(s['end'])}"
            )
            lines.append(text)
            lines.append("")

        return "\n".join(lines)

    def to_vtt(self, segments: List[Dict[str, Any]]) -> str:
        """Convert segments to WebVTT subtitle format.

        Args:
            segments: List of transcript segments with start/end times

        Returns:
            VTT formatted string
        """
        lines = ["WEBVTT", ""]

        for s in segments:
            speaker = s.get("speaker")
            text = s["text"].strip()
            if speaker:
                text = f"[{speaker}] {text}"

            # VTT uses period for milliseconds, not comma
            start_ts = format_timestamp(s["start"]).replace(",", ".")
            end_ts = format_timestamp(s["end"]).replace(",", ".")

            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(text)
            lines.append("")

        return "\n".join(lines)

    def to_md(self, segments: List[Dict[str, Any]]) -> str:
        """Convert segments to Markdown format.

        Args:
            segments: List of transcript segments

        Returns:
            Markdown formatted string
        """
        paragraphs = [s["text"].strip() for s in segments]
        content = "# Transcript\n\n" + "\n\n".join(paragraphs) + "\n"
        return content

    def export(
        self,
        transcript: Dict[str, Any],
        formats: List[str],
        output_dir: Path,
        base_name: str = "transcript",
        replace: bool = False,
    ) -> Dict[str, Any]:
        """Export transcript to multiple formats.

        Args:
            transcript: Transcript data with segments
            formats: List of format names (txt, srt, vtt, md)
            output_dir: Directory to write files to
            base_name: Base filename (without extension)
            replace: Only overwrite files if content changed

        Returns:
            Dict with export results (files written, segments count)

        Raises:
            ExportError: If export fails
        """
        segments = transcript.get("segments")
        if not segments:
            raise ExportError("Transcript missing 'segments' field")

        # Validate formats
        valid_formats = {"txt", "srt", "vtt", "md"}
        invalid = set(formats) - valid_formats
        if invalid:
            raise ExportError(
                f"Invalid formats: {', '.join(invalid)}. Valid: {', '.join(valid_formats)}"
            )

        output_files = {}
        files_written = 0

        # Generate each requested format
        for fmt in formats:
            self._report_progress(f"Generating {fmt.upper()} format")

            if fmt == "txt":
                content = self.to_txt(segments)
                out_path = output_dir / f"{base_name}.txt"
            elif fmt == "srt":
                content = self.to_srt(segments)
                out_path = output_dir / f"{base_name}.srt"
            elif fmt == "vtt":
                content = self.to_vtt(segments)
                out_path = output_dir / f"{base_name}.vtt"
            elif fmt == "md":
                content = self.to_md(segments)
                out_path = output_dir / f"{base_name}.md"
            else:
                continue

            # Write file
            if write_if_changed(out_path, content, replace):
                files_written += 1

            output_files[fmt] = str(out_path)

        return {
            "formats": formats,
            "output_dir": str(output_dir),
            "files": output_files,
            "files_written": files_written,
            "segments_count": len(segments),
        }


# Convenience function for direct use
def export_transcript(
    transcript: Dict[str, Any],
    formats: List[str],
    output_dir: Path,
    base_name: str = "transcript",
    replace: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Export transcript to multiple formats.

    Args:
        transcript: Transcript data
        formats: Format names (txt, srt, vtt, md)
        output_dir: Output directory
        base_name: Base filename
        replace: Only overwrite if changed
        progress_callback: Optional progress callback

    Returns:
        Dict with export results
    """
    engine = ExportEngine(progress_callback=progress_callback)
    return engine.export(transcript, formats, output_dir, base_name, replace)
