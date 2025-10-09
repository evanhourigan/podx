#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from .cli_shared import print_json, read_stdin_json
from .logging import get_logger
from .schemas import Segment, Transcript
from .validation import validate_output

logger = get_logger(__name__)


def merge_segments(segments: List[Dict[str, Any]], max_gap: float = 1.0, max_len: int = 800) -> List[Dict[str, Any]]:
    if not segments:
        return []
    merged: List[Dict[str, Any]] = []
    current = {"text": segments[0]["text"], "start": segments[0]["start"], "end": segments[0]["end"]}
    for seg in segments[1:]:
        gap = float(seg["start"]) - float(current["end"])  # type: ignore[index]
        if gap < max_gap and len(current["text"]) + len(seg["text"]) < max_len:
            current["text"] += " " + seg["text"]
            current["end"] = seg["end"]
        else:
            merged.append(current)
            current = {"text": seg["text"], "start": seg["start"], "end": seg["end"]}
    merged.append(current)
    return merged


def normalize_text(text: str) -> str:
    import re

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([.?!])([A-Za-z])", r"\1 \2", text)
    return text.strip()


def normalize_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for s in segments:
        s["text"] = normalize_text(s.get("text", ""))
    return segments


@click.command()
@click.option("--input", "input_file", type=click.Path(exists=True, path_type=Path), help="Read Transcript JSON from file instead of stdin")
@click.option("--output", "output_file", type=click.Path(path_type=Path), help="Write processed Transcript JSON to file (also prints to stdout)")
@click.option("--merge", "do_merge", is_flag=True, help="Merge adjacent short segments for readability")
@click.option("--normalize", "do_normalize", is_flag=True, help="Normalize whitespace and punctuation in text")
@click.option("--max-gap", type=float, default=1.0, help="Max gap (sec) to merge segments")
@click.option("--max-len", type=int, default=800, help="Max merged text length (chars)")
@validate_output(Transcript)
def main(input_file: Optional[Path], output_file: Optional[Path], do_merge: bool, do_normalize: bool, max_gap: float, max_len: int):
    """
    Preprocess a Transcript JSON by merging segments and normalizing text.
    This is a non-destructive cleanup step before downstream analysis.
    """
    raw = json.loads(input_file.read_text()) if input_file else read_stdin_json()
    if not raw or "segments" not in raw:
        raise SystemExit("input must contain Transcript JSON with 'segments' field")

    # Copy through metadata fields
    out: Dict[str, Any] = {
        "audio_path": raw.get("audio_path"),
        "language": raw.get("language"),
        "asr_model": raw.get("asr_model"),
        "asr_provider": raw.get("asr_provider"),
        "preset": raw.get("preset"),
        "decoder_options": raw.get("decoder_options"),
    }

    segs = raw.get("segments", [])
    if do_merge:
        segs = merge_segments(segs, max_gap=max_gap, max_len=max_len)
    if do_normalize:
        segs = normalize_segments(segs)

    # Validate segments
    validated_segments: List[Dict[str, Any]] = []
    for s in segs:
        try:
            validated = Segment.parse_obj(s)
            validated_segments.append(validated.dict())
        except Exception as e:
            logger.debug("Dropping invalid segment", error=str(e))

    out["segments"] = validated_segments
    out["text"] = "\n".join([s["text"] for s in validated_segments]).strip()

    if output_file:
        output_file.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print_json(out)
    return out


if __name__ == "__main__":
    main()


