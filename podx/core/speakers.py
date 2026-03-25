"""Speaker mapping persistence and application.

Decouples speaker identification from diarization so speaker maps
can be saved, loaded, and reapplied independently without re-running
pyannote diarization.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..logging import get_logger

logger = get_logger(__name__)

SPEAKER_MAP_FILENAME = "speaker-map.json"
GENERIC_SPEAKER_PATTERN = re.compile(r"^SPEAKER_\d+$")


def save_speaker_map(episode_dir: Path, speaker_map: Dict[str, str]) -> Path:
    """Save speaker mapping to speaker-map.json.

    Args:
        episode_dir: Episode directory
        speaker_map: Mapping of SPEAKER_XX -> real name

    Returns:
        Path to saved file
    """
    path = episode_dir / SPEAKER_MAP_FILENAME
    path.write_text(json.dumps(speaker_map, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved speaker map", path=str(path), speakers=len(speaker_map))
    return path


def load_speaker_map(episode_dir: Path) -> Optional[Dict[str, str]]:
    """Load speaker mapping from speaker-map.json if it exists.

    Args:
        episode_dir: Episode directory

    Returns:
        Speaker map dict or None if file doesn't exist
    """
    path = episode_dir / SPEAKER_MAP_FILENAME
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return None
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load speaker map", path=str(path), error=str(e))
        return None


def apply_speaker_map_to_transcript(
    episode_dir: Path,
    speaker_map: Dict[str, str],
    save_transcript: bool = True,
) -> bool:
    """Apply speaker mapping to transcript.json.

    Loads transcript.json, applies speaker names, and optionally saves back.

    Args:
        episode_dir: Episode directory
        speaker_map: Mapping of SPEAKER_XX -> real name
        save_transcript: Whether to save the modified transcript

    Returns:
        True if transcript was modified
    """
    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        logger.warning("No transcript.json found", path=str(episode_dir))
        return False

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments = transcript.get("segments", [])

    modified = False
    for seg in segments:
        old_speaker = seg.get("speaker", "")
        if old_speaker and old_speaker in speaker_map:
            seg["speaker"] = speaker_map[old_speaker]
            modified = True

    if modified and save_transcript:
        transcript_path.write_text(
            json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Applied speaker map to transcript", speakers=len(speaker_map))

    return modified


def has_generic_speakers(episode_dir: Path) -> bool:
    """Check if transcript.json has generic SPEAKER_XX labels.

    Args:
        episode_dir: Episode directory

    Returns:
        True if any segment has a SPEAKER_XX style ID
    """
    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        return False

    try:
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
        segments = transcript.get("segments", [])
        return _segments_have_generic_speakers(segments)
    except (json.JSONDecodeError, OSError):
        return False


def _segments_have_generic_speakers(segments: List[Dict[str, Any]]) -> bool:
    """Check if segments list contains generic SPEAKER_XX labels."""
    for seg in segments:
        speaker = seg.get("speaker", "")
        if speaker and GENERIC_SPEAKER_PATTERN.match(speaker):
            return True
    return False
