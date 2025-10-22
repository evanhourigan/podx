"""Interactive browser for selecting transcripts to preprocess."""

import json
from pathlib import Path
from typing import Any, Dict, List

from ..logging import get_logger

logger = get_logger(__name__)


def scan_preprocessable_transcripts(scan_dir: Path) -> List[Dict[str, Any]]:
    """
    Scan directory for preprocessable transcripts.

    For each ASR model, returns the MOST PROCESSED non-preprocessed version:
    - Priority: diarized > aligned > base

    Returns list with one entry per model, indicating if preprocessed version exists.
    """
    from collections import defaultdict

    transcripts_by_model = defaultdict(lambda: {
        "base": None,
        "aligned": None,
        "diarized": None,
        "preprocessed": None
    })

    # Collect all transcript files grouped by model
    for transcript_file in scan_dir.rglob("transcript-*.json"):
        try:
            filename = transcript_file.stem

            # Determine type and extract model name
            if filename.startswith("transcript-preprocessed-"):
                asr_model = filename[len("transcript-preprocessed-"):]
                transcript_type = "preprocessed"
            elif filename.startswith("transcript-diarized-"):
                asr_model = filename[len("transcript-diarized-"):]
                transcript_type = "diarized"
            elif filename.startswith("transcript-aligned-"):
                asr_model = filename[len("transcript-aligned-"):]
                transcript_type = "aligned"
            elif filename.startswith("transcript-"):
                asr_model = filename[len("transcript-"):]
                transcript_type = "base"
            else:
                continue

            # Load transcript data
            transcript_data = json.loads(transcript_file.read_text(encoding="utf-8"))

            # Get audio path
            audio_path = transcript_data.get("audio_path")
            if not audio_path:
                continue

            audio_path = Path(audio_path)
            if not audio_path.exists():
                continue

            # Try to get episode metadata for better display
            episode_meta_file = transcript_file.parent / "episode-meta.json"
            episode_meta = {}
            if episode_meta_file.exists():
                try:
                    episode_meta = json.loads(
                        episode_meta_file.read_text(encoding="utf-8")
                    )
                except Exception:
                    episode_meta = {}

            # Store this transcript variant
            transcripts_by_model[asr_model][transcript_type] = {
                "transcript_file": transcript_file,
                "transcript_data": transcript_data,
                "audio_path": audio_path,
                "asr_model": asr_model,
                "type": transcript_type,
                "episode_meta": episode_meta,
                "directory": transcript_file.parent,
            }

        except Exception as e:
            logger.debug(f"Failed to parse {transcript_file}: {e}")
            continue

    # For each model, select the most processed non-preprocessed version
    result = []
    for asr_model, variants in transcripts_by_model.items():
        # Priority: diarized > aligned > base
        if variants["diarized"]:
            selected = variants["diarized"]
            source_type = "diarized"
        elif variants["aligned"]:
            selected = variants["aligned"]
            source_type = "aligned"
        elif variants["base"]:
            selected = variants["base"]
            source_type = "base"
        else:
            continue  # No valid source transcript for this model

        # Check if preprocessed version exists
        is_preprocessed = variants["preprocessed"] is not None

        # Build preprocessed filename path
        preprocessed_file = selected["directory"] / f"transcript-preprocessed-{asr_model}.json"

        # Create display string showing model and source type
        model_display = f"{asr_model} ({source_type})"

        result.append({
            "transcript_file": selected["transcript_file"],
            "transcript_data": selected["transcript_data"],
            "audio_path": selected["audio_path"],
            "asr_model": asr_model,
            "source_type": source_type,  # "base", "aligned", or "diarized"
            "model_display": model_display,  # Combined display: "large-v3 (diarized)"
            "is_preprocessed": is_preprocessed,
            "preprocessed_file": preprocessed_file,
            "episode_meta": selected["episode_meta"],
            "directory": selected["directory"],
        })

    # Sort by date (most recent first) then by show name
    def sort_key(t):
        date_str = t["episode_meta"].get("episode_published", "")
        return (date_str, t["episode_meta"].get("show", ""))

    result.sort(key=sort_key, reverse=True)
    return result
