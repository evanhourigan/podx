"""File and filename utilities for podx."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional


def discover_transcripts(dir_path: Path) -> Dict[str, Path]:
    """Scan directory for transcript files and return mapping of asr_model to file path.

    Searches for both model-specific transcripts (transcript-*.json) and legacy transcript.json.
    Determines ASR model from JSON content rather than filename.

    Args:
        dir_path: Directory to scan for transcript files

    Returns:
        Dictionary mapping ASR model name to transcript file path
    """
    found: Dict[str, Path] = {}

    # Scan for model-specific transcripts
    for path in dir_path.glob("transcript-*.json"):
        try:
            data = json.loads(path.read_text())
            asr_model_val = data.get("asr_model") or "unknown"
            found[asr_model_val] = path
        except Exception:
            continue

    # Check for legacy transcript.json
    legacy = dir_path / "transcript.json"
    if legacy.exists():
        try:
            data = json.loads(legacy.read_text())
            asr_model_val = data.get("asr_model") or "unknown"
            found[asr_model_val] = legacy
        except Exception:
            found["unknown"] = legacy

    return found


def sanitize_model_name(name: str) -> str:
    """Sanitize model name for safe use in filenames.

    Replaces all non-alphanumeric characters (except . _ -) with underscores.
    Useful for converting model names like "gpt-4.0" or "large-v3:turbo" to safe filenames.

    Args:
        name: Model name to sanitize

    Returns:
        Sanitized model name safe for filenames
    """
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def sanitize_filename(s: str) -> str:
    """Sanitize a string for safe use in filenames.

    Keeps spaces, only replaces truly problematic characters for filesystems.

    Args:
        s: String to sanitize

    Returns:
        Sanitized string safe for filenames
    """
    # Keep spaces, only replace characters that are invalid on most filesystems
    return re.sub(r'[<>:"/\\|?*]', "_", s.strip())


def generate_workdir(show_name: str, episode_date: str, title: str = "") -> Path:
    """Generate a work directory path based on show name, date, and optional title.

    Creates URL-safe directory structure: show_name/YYYY-MM-DD-title-slug

    Args:
        show_name: Name of the podcast show
        episode_date: Episode publication date (will be parsed and formatted)
        title: Optional episode title (will be slugified and truncated to 20 chars)

    Returns:
        Path object for the work directory
    """
    from slugify import slugify

    # Sanitize show name for filesystem (using slugify for consistency)
    safe_show = slugify(show_name, separator="_")

    # Parse and format date
    try:
        from dateutil import parser as dtparse

        parsed_date = dtparse.parse(episode_date)
        date_str = parsed_date.strftime("%Y-%m-%d")
    except Exception:
        # Fallback to original date string if parsing fails
        date_str = sanitize_filename(episode_date)

    # Add slugified title if provided
    if title:
        # Truncate to 20 chars before slugifying to keep URL manageable
        truncated = title[:20].strip()
        title_slug = slugify(truncated, separator="-")
        if title_slug:  # Only add if slugification produced something
            date_str = f"{date_str}-{title_slug}"

    return Path(safe_show) / date_str


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds to HH:MM:SS format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (HH:MM:SS) or "Unknown" if None
    """
    if not seconds:
        return "Unknown"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_date(date_str: str) -> str:
    """Format date string to readable YYYY-MM-DD format.

    Args:
        date_str: Date string in various formats

    Returns:
        Formatted date string (YYYY-MM-DD) or original string if parsing fails
    """
    try:
        # Parse various date formats
        for fmt in [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
        ]:
            try:
                from datetime import datetime

                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Try dateutil parser as fallback
        try:
            from dateutil import parser as dtparse

            dt = dtparse.parse(date_str)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    except Exception:
        pass

    # Return original if all parsing fails
    return date_str[:10] if len(date_str) >= 10 else date_str


def build_preprocess_command(output_path: Path, restore: bool = False) -> List[str]:
    """Build podx-preprocess command with merge and normalize flags.

    Args:
        output_path: Output file path for processed transcript
        restore: Whether to include --restore flag for semantic restoration

    Returns:
        List of command arguments for podx-preprocess
    """
    cmd = [
        "podx-preprocess",
        "--output",
        str(output_path),
        "--merge",
        "--normalize",
    ]
    if restore:
        cmd.append("--restore")
    return cmd


def build_deepcast_command(
    input_path: Path,
    output_path: Path,
    model: str,
    temperature: float,
    meta_path: Path | None = None,
    analysis_type: str | None = None,
    extract_markdown: bool = False,
    generate_pdf: bool = False,
) -> List[str]:
    """Build podx-deepcast command for AI transcript analysis.

    Args:
        input_path: Input transcript file path
        output_path: Output deepcast JSON file path
        model: AI model name (e.g., "gpt-4", "claude-3")
        temperature: Model temperature (0.0-1.0)
        meta_path: Optional episode metadata file path
        analysis_type: Optional analysis type (e.g., "interview", "panel_discussion")
        extract_markdown: Whether to extract markdown from analysis
        generate_pdf: Whether to generate PDF output

    Returns:
        List of command arguments for podx-deepcast
    """
    cmd = [
        "podx-deepcast",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--model",
        model,
        "--temperature",
        str(temperature),
    ]
    if meta_path and meta_path.exists():
        cmd.extend(["--meta", str(meta_path)])
    if analysis_type:
        cmd.extend(["--type", analysis_type])
    if extract_markdown:
        cmd.append("--extract-markdown")
    if generate_pdf:
        cmd.append("--pdf")
    return cmd
