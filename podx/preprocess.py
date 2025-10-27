#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from .cli_shared import print_json, read_stdin_json
from .logging import get_logger
from .schemas import Segment, Transcript
from .ui.preprocess_browser import PreprocessTwoPhase
from .validation import validate_output

try:
    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False

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


def _semantic_restore_segments(texts: List[str], model: str, batch_size: int = 20) -> List[str]:
    # Best-effort import: support both new and legacy OpenAI SDKs
    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI()
        use_new = True
    except Exception:
        import openai  # type: ignore
        use_new = False

    prompt = (
        "You are cleaning up noisy ASR transcript text.\n"
        "- Fix grammar and punctuation.\n"
        "- Preserve every idea and clause, even incomplete ones.\n"
        "- Do NOT remove filler words that imply transitions.\n"
        "Return only the cleaned text."
    )

    out: List[str] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]

        # Batch processing: join texts with delimiter, send as single request
        delimiter = "\n---SEGMENT---\n"
        batch_text = delimiter.join(chunk)
        batch_prompt = (
            f"Clean up these {len(chunk)} transcript segments. "
            f"Return them in the same order, separated by '{delimiter.strip()}'.\n\n"
            f"{batch_text}"
        )

        if use_new:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": batch_prompt},
                ],
            )
            batch_result = resp.choices[0].message.content or ""
        else:
            resp = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": batch_prompt},
                ],
            )
            batch_result = resp.choices[0].message.get("content") or ""

        # Split response back into individual cleaned texts
        cleaned_chunks = batch_result.split(delimiter)

        # Handle case where LLM doesn't return exact number of segments
        # (fallback to original texts if mismatch)
        if len(cleaned_chunks) == len(chunk):
            out.extend([c.strip() for c in cleaned_chunks])
        else:
            # Fallback: if batch processing failed, keep originals
            logger.warning(
                f"Batch restore returned {len(cleaned_chunks)} segments, expected {len(chunk)}. "
                "Using original texts for this batch."
            )
            out.extend(chunk)

    return out


@click.command()
@click.option("--input", "-i", "input_file", type=click.Path(exists=True, path_type=Path), help="Read Transcript JSON from file instead of stdin")
@click.option("--output", "-o", "output_file", type=click.Path(path_type=Path), help="Write processed Transcript JSON to file (also prints to stdout)")
@click.option("--merge", "do_merge", is_flag=True, help="Merge adjacent short segments for readability")
@click.option("--normalize", "do_normalize", is_flag=True, help="Normalize whitespace and punctuation in text")
@click.option("--max-gap", type=float, default=1.0, help="Max gap (sec) to merge segments")
@click.option("--max-len", type=int, default=800, help="Max merged text length (chars)")
@click.option("--restore", "do_restore", is_flag=True, help="Semantic restore text using an LLM (preserve meaning, fix grammar)")
@click.option("--restore-model", default="gpt-4.1-mini", help="Model for semantic restore (when --restore)")
@click.option("--restore-batch-size", type=int, default=20, help="Segments per restore request")
@click.option("--interactive", is_flag=True, help="Interactive browser to select transcripts for preprocessing")
@click.option("--scan-dir", type=click.Path(exists=True, path_type=Path), default=".", help="Directory to scan for transcripts (default: current directory)")
@validate_output(Transcript)
def main(input_file: Optional[Path], output_file: Optional[Path], do_merge: bool, do_normalize: bool, max_gap: float, max_len: int, do_restore: bool, restore_model: str, restore_batch_size: int, interactive: bool, scan_dir: Path):
    """
    Preprocess a Transcript JSON by merging segments and normalizing text.
    This is a non-destructive cleanup step before downstream analysis.
    """
    # Interactive mode: browse transcripts and select one
    if interactive:
        if not RICH_AVAILABLE:
            raise SystemExit("Interactive mode requires rich library. Install with: pip install rich")

        # Two-phase selection: episode → most-processed transcript
        logger.info(f"Scanning for episodes in: {scan_dir}")
        browser = PreprocessTwoPhase(scan_dir=Path(scan_dir))
        selected = browser.browse()

        if not selected:
            logger.info("User cancelled transcript selection")
            print("❌ Transcript pre-processing cancelled")
            raise SystemExit(0)

        # Extract transcript and config from result
        transcript_info = selected.get("transcript")
        config = selected.get("config")

        if not config:
            logger.info("User cancelled preprocessing configuration")
            print("❌ Transcript pre-processing cancelled")
            raise SystemExit(0)

        # Use config from modal
        do_merge = config.get("merge", False)
        do_normalize = config.get("normalize", False)
        do_restore = config.get("restore", False)

        # Show what will be done
        steps_to_apply = []
        if do_merge:
            steps_to_apply.append("merge")
        if do_normalize:
            steps_to_apply.append("normalize")
        if do_restore:
            steps_to_apply.append("restore")

        if not steps_to_apply:
            print("❌ No preprocessing steps selected")
            raise SystemExit(0)

        print(f"\n⏳ Applying: {' + '.join(steps_to_apply)}")
        if do_restore:
            print("   (This may take a while due to LLM processing...)")
        print()

        raw = transcript_info.get("transcript_data")
        # Choose output next to transcript
        outdir = transcript_info.get("directory")
        asr = transcript_info.get("asr_model", "model")
        output_file = outdir / f"transcript-preprocessed-{asr}.json"
    else:
        raw = json.loads(input_file.read_text()) if input_file else read_stdin_json()
    if not raw or "segments" not in raw:
        raise SystemExit("input must contain Transcript JSON with 'segments' field")

    # Copy through metadata fields
    out: Dict[str, Any] = {
        "audio_path": raw.get("audio_path"),
        "language": raw.get("language"),
        "asr_model": raw.get("asr_model"),
        "asr_provider": raw.get("asr_provider"),
        "decoder_options": raw.get("decoder_options"),
    }

    segs = raw.get("segments", [])
    if do_merge:
        segs = merge_segments(segs, max_gap=max_gap, max_len=max_len)
    if do_normalize:
        segs = normalize_segments(segs)

    if do_restore and segs:
        try:
            restored_texts = _semantic_restore_segments([s.get("text", "") for s in segs], restore_model, batch_size=restore_batch_size)
            for i, txt in enumerate(restored_texts):
                segs[i]["text"] = txt
        except Exception as e:
            logger.warning("Semantic restore failed; continuing without it", error=str(e))

    # Validate segments
    validated_segments: List[Dict[str, Any]] = []
    for s in segs:
        try:
            validated = Segment.model_validate(s)
            validated_segments.append(validated.model_dump())
        except Exception as e:
            logger.debug("Dropping invalid segment", error=str(e))

    out["segments"] = validated_segments
    out["text"] = "\n".join([s["text"] for s in validated_segments]).strip()

    if output_file:
        output_file.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        # In interactive mode, print completion message
        if interactive:
            steps_applied = []
            if do_merge:
                steps_applied.append("merge")
            if do_normalize:
                steps_applied.append("normalize")
            if do_restore:
                steps_applied.append("restore")
            steps_str = " + ".join(steps_applied) if steps_applied else "none"
            print("✅ Preprocessing complete")
            print(f"   Steps: {steps_str}")
            print(f"   Output: {output_file}")

    # Only print JSON in non-interactive mode (for piping/scripting)
    if not interactive:
        print_json(out)
    return out


if __name__ == "__main__":
    main()
