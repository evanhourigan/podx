#!/usr/bin/env python3
"""CLI wrapper for preprocess command.

Thin Click wrapper that uses core.preprocess.TranscriptPreprocessor for actual logic.
Handles CLI arguments, input/output, and interactive mode.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from podx.cli.cli_shared import print_json, read_stdin_json
from podx.core.preprocess import PreprocessError, TranscriptPreprocessor
from podx.logging import get_logger
from podx.schemas import Segment, Transcript
from podx.ui.preprocess_browser import PreprocessTwoPhase
from podx.validation import validate_output

try:
    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False

logger = get_logger(__name__)


@click.command()
@click.option(
    "--input",
    "-i",
    "input_file",
    type=click.Path(exists=True, path_type=Path),
    help="Read Transcript JSON from file instead of stdin",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(path_type=Path),
    help="Write processed Transcript JSON to file (also prints to stdout)",
)
@click.option(
    "--merge",
    "do_merge",
    is_flag=True,
    help="Merge adjacent short segments for readability",
)
@click.option(
    "--normalize",
    "do_normalize",
    is_flag=True,
    help="Normalize whitespace and punctuation in text",
)
@click.option(
    "--max-gap", type=float, default=1.0, help="Max gap (sec) to merge segments"
)
@click.option(
    "--max-len", type=int, default=800, help="Max merged text length (chars)"
)
@click.option(
    "--restore",
    "do_restore",
    is_flag=True,
    help="Semantic restore text using an LLM (preserve meaning, fix grammar)",
)
@click.option(
    "--restore-model",
    default="gpt-4.1-mini",
    help="Model for semantic restore (when --restore)",
)
@click.option(
    "--restore-batch-size",
    type=int,
    default=20,
    help="Segments per restore request",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive browser to select transcripts for preprocessing",
)
@click.option(
    "--scan-dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Directory to scan for transcripts (default: current directory)",
)
@validate_output(Transcript)
def main(
    input_file: Optional[Path],
    output_file: Optional[Path],
    do_merge: bool,
    do_normalize: bool,
    max_gap: float,
    max_len: int,
    do_restore: bool,
    restore_model: str,
    restore_batch_size: int,
    interactive: bool,
    scan_dir: Path,
):
    """
    Preprocess a Transcript JSON by merging segments and normalizing text.
    This is a non-destructive cleanup step before downstream analysis.
    """
    # Interactive mode: browse transcripts and select one
    if interactive:
        if not RICH_AVAILABLE:
            raise SystemExit(
                "Interactive mode requires rich library. Install with: pip install rich"
            )

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
        raw = (
            json.loads(input_file.read_text()) if input_file else read_stdin_json()
        )

    if not raw or "segments" not in raw:
        raise SystemExit("input must contain Transcript JSON with 'segments' field")

    # Use core preprocessor (pure business logic)
    try:
        preprocessor = TranscriptPreprocessor(
            merge=do_merge,
            normalize=do_normalize,
            restore=do_restore,
            max_gap=max_gap,
            max_len=max_len,
            restore_model=restore_model,
            restore_batch_size=restore_batch_size,
        )
        out = preprocessor.preprocess(raw)
    except (PreprocessError, ValueError) as e:
        raise SystemExit(str(e))

    # Validate segments
    validated_segments: List[Dict[str, Any]] = []
    for s in out.get("segments", []):
        try:
            validated = Segment.model_validate(s)
            validated_segments.append(validated.model_dump())
        except Exception as e:
            logger.debug("Dropping invalid segment", error=str(e))

    out["segments"] = validated_segments

    # Write output
    if output_file:
        output_file.write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
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
