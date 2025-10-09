#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from .cli_shared import print_json, read_stdin_json
from .logging import get_logger
from .schemas import Segment, Transcript
from .validation import validate_output
from .align import scan_alignable_transcripts

try:
    from rich.console import Console
    from rich.table import Table
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
        for text in chunk:
            if use_new:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text},
                    ],
                )
                cleaned = resp.choices[0].message.content or ""
            else:
                resp = openai.ChatCompletion.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text},
                    ],
                )
                cleaned = resp.choices[0].message.get("content") or ""
            out.append(cleaned)
    return out


@click.command()
@click.option("--input", "input_file", type=click.Path(exists=True, path_type=Path), help="Read Transcript JSON from file instead of stdin")
@click.option("--output", "output_file", type=click.Path(path_type=Path), help="Write processed Transcript JSON to file (also prints to stdout)")
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
        console = Console()
        console.print(f"[dim]Scanning for transcripts in: {scan_dir}[/dim]")
        transcripts = scan_alignable_transcripts(Path(scan_dir))
        if not transcripts:
            console.print(f"[red]No transcripts found in {scan_dir}[/red]")
            raise SystemExit("No transcript-*.json files found")

        table = Table(show_header=True, header_style="bold magenta", title="🎙️ Transcripts Available for Preprocess")
        table.add_column("#", style="cyan", width=3, justify="right")
        table.add_column("ASR", style="yellow", width=10)
        table.add_column("Show", style="green", width=18)
        table.add_column("Date", style="blue", width=12)
        table.add_column("Title", style="white", width=45)

        for idx, item in enumerate(transcripts, start=1):
            asr = item.get("asr_model", "?")
            meta = item.get("episode_meta", {})
            show = meta.get("show", "Unknown")
            date = meta.get("episode_published", "Unknown")
            title = meta.get("episode_title", "Unknown")
            table.add_row(str(idx), asr, show, date[:10], title)

        console.print(table)
        choice = input(f"\n👉 Select transcript (1-{len(transcripts)}) or Q to cancel: ").strip().upper()
        if choice in ["Q", "QUIT", "EXIT"]:
            console.print("[dim]Cancelled[/dim]")
            raise SystemExit(0)
        try:
            sel = int(choice)
            if not (1 <= sel <= len(transcripts)):
                raise ValueError("out of range")
        except Exception:
            console.print("[red]Invalid selection[/red]")
            raise SystemExit(1)

        selected = transcripts[sel - 1]
        raw = selected.get("transcript_data")
        # Choose output next to transcript
        outdir = selected.get("directory")
        asr = selected.get("asr_model", "model")
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
        "preset": raw.get("preset"),
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


