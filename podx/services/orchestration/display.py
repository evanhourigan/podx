"""Display formatting utilities for pipeline configuration and results."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from podx.constants import DEFAULT_ENCODING, JSON_INDENT, OPENAI_MODEL_PREFIX
from podx.logging import get_logger

logger = get_logger(__name__)


def display_pipeline_config(
    align: bool,
    diarize: bool,
    deepcast: bool,
    notion: bool,
    show: Optional[str],
    rss_url: Optional[str],
    date: Optional[str],
    model: str,
    compute: str,
) -> list[str]:
    """Display pipeline configuration and return list of steps.

    Builds the list of pipeline steps based on enabled features, logs the
    configuration, and displays it to the user.

    Args:
        align: Whether alignment is enabled
        diarize: Whether diarization is enabled
        deepcast: Whether deepcast analysis is enabled
        notion: Whether Notion upload is enabled
        show: Podcast show name
        rss_url: RSS feed URL
        date: Episode date filter
        model: ASR model name
        compute: Compute type

    Returns:
        List of pipeline step names
    """
    from podx.cli.services.progress import print_podx_info

    steps = ["fetch", "transcode", "transcribe"]
    if align:
        steps.append("align")
    if diarize:
        steps.append("diarize")
    if deepcast:
        steps.append("deepcast")
    if notion:
        steps.append("notion")

    logger.info(
        "Starting pipeline",
        steps=steps,
        show=show,
        rss_url=rss_url,
        date=date,
        model=model,
        compute=compute,
    )

    print_podx_info(f"Pipeline: {' → '.join(steps)}")

    return steps


def print_results_summary(
    start_time: float,
    steps: List[str],
    wd: Path,
    results: Dict[str, Any],
) -> None:
    """Print final pipeline summary with key results and JSON output.

    Displays completion message with total duration, key output files,
    and JSON results for programmatic use.

    Args:
        start_time: Pipeline start timestamp
        steps: List of pipeline steps that were executed
        wd: Working directory Path
        results: Results dictionary with output file paths

    Side Effects:
        - Logs completion info
        - Prints success message with duration
        - Prints key file paths with emojis
        - Prints full results as JSON
    """
    from podx.cli.services.progress import format_duration, print_podx_info, print_podx_success

    # Final summary
    total_time = time.time() - start_time
    logger.info(
        "Pipeline completed",
        total_duration=total_time,
        steps_completed=len(steps),
        workdir=str(wd),
    )

    print_podx_success(f"Pipeline completed in {format_duration(total_time)}")

    # Show key results
    key_files = []
    if "latest_txt" in results:
        key_files.append(f"📄 Transcript: {results['latest_txt']}")
    if "latest_srt" in results:
        key_files.append(f"📺 Subtitles: {results['latest_srt']}")
    if "deepcast_md" in results:
        key_files.append(f"🤖 Analysis: {results['deepcast_md']}")
    if "notion" in results:
        key_files.append(f"☁️ Notion: {results['notion']}")

    if key_files:
        print_podx_info("\n".join(key_files))

    # Still print JSON for programmatic use
    print(json.dumps(results, indent=JSON_INDENT))


def build_episode_metadata_display(
    selected: Dict[str, Any], meta: Dict[str, Any], config: Dict[str, Any]
) -> str:
    """Build episode metadata display for preview panel.

    Args:
        selected: Selected episode dictionary from scan
        meta: Episode metadata from episode-meta.json
        config: Pipeline configuration (for cost estimation)

    Returns:
        Formatted metadata string
    """
    from podx.utils.file_utils import format_duration

    # Basic metadata
    show = selected.get("show", "Unknown")
    date = selected.get("date", "Unknown")
    title = selected.get("title", "Unknown")

    # Get duration from transcript if available
    duration_seconds = None
    sel_dir = selected.get("directory")
    transcript_json = None
    if sel_dir:
        latest_path = sel_dir / "latest.json"
        if latest_path.exists():
            try:
                transcript_json = json.loads(latest_path.read_text(encoding=DEFAULT_ENCODING))
                segments = transcript_json.get("segments", [])
                if segments:
                    duration_seconds = int(max(s.get("end", 0) for s in segments))
            except Exception:
                pass

    # If no transcript, try to get from audio file using ffprobe
    if duration_seconds is None and sel_dir:
        audio_path = meta.get("audio_path")
        if audio_path and Path(audio_path).exists():
            try:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        audio_path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    duration_seconds = int(float(result.stdout.strip()))
            except Exception:
                pass

    duration_str = format_duration(duration_seconds)

    # Processing status
    num_transcripts = len(selected.get("transcripts", []))
    num_aligned = len(selected.get("aligned", []))
    num_diarized = len(selected.get("diarized", []))
    num_deepcasts = len(selected.get("deepcasts", []))
    has_consensus = selected.get("has_consensus", False)
    last_run = selected.get("last_run", "Never")

    # Build processing summary
    processing_parts = []
    if num_transcripts > 0:
        processing_parts.append(f"{num_transcripts} transcript{'s' if num_transcripts > 1 else ''}")
    if num_aligned > 0:
        processing_parts.append(f"{num_aligned} aligned")
    if num_diarized > 0:
        processing_parts.append(f"{num_diarized} diarized")
    if num_deepcasts > 0:
        processing_parts.append(f"{num_deepcasts} deepcast{'s' if num_deepcasts > 1 else ''}")
    if has_consensus:
        processing_parts.append("consensus")

    if processing_parts:
        processing_status = f"Existing: {', '.join(processing_parts)}"
        processing_status += f"\nLast run: {last_run}"
    else:
        processing_status = "No existing processed versions"

    # Cost estimate (if deepcast enabled and transcript available)
    cost_str = ""
    if config.get("deepcast") and transcript_json:
        try:
            from podx.cli.deepcast import estimate_deepcast_cost
            from podx.cli.model_catalog import load_model_catalog

            provider = (
                "openai"
                if config["deepcast_model"].startswith(OPENAI_MODEL_PREFIX)
                or "-" in config["deepcast_model"]
                else "anthropic"
            )
            catalog = load_model_catalog(refresh=False)
            est = estimate_deepcast_cost(
                transcript_json, provider, config["deepcast_model"], catalog
            )
            cost_str = f"\nEstimated cost: ${est.total_usd:.2f} (in≈{est.input_tokens:,} tok, out≈{est.output_tokens:,} tok)"
        except Exception:
            pass

    # Build final display
    metadata = (
        f"Show: {show}\n"
        f"Title: {title}\n"
        f"Released: {date}\n"
        f"Duration: {duration_str}"
        f"{cost_str}\n"
        f"\n{processing_status}"
    )

    return metadata
