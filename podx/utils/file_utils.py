"""File and filename utilities for podx."""

import json
import re
from pathlib import Path
from typing import Dict


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
