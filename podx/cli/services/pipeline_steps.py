"""Pipeline execution steps for podcast processing orchestration.

Contains all execution functions for the complete podcast processing pipeline,
including fetch, transcription, enhancement, analysis, export, and cleanup.
Each function represents a discrete pipeline step that can be resumed or skipped.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from rich.panel import Panel

from podx.cli.services import CommandBuilder, run_command
from podx.constants import (
    DEFAULT_ENCODING,
    JSON_INDENT,
    OPENAI_MODEL_PREFIX,
    TITLE_MAX_LENGTH,
)
from podx.errors import ValidationError
from podx.logging import get_logger

logger = get_logger(__name__)

# Alias _run for consistency with original code
_run = run_command


def execute_fetch(
    config: dict,
    interactive_mode_meta: dict | None,
    interactive_mode_wd: Path | None,
    progress,
    verbose: bool,
) -> tuple[dict, Path]:
    """Execute fetch step to get episode metadata and determine working directory.

    Handles three fetch modes:
    1. Interactive mode: Use pre-loaded metadata and workdir (skip fetch)
    2. YouTube mode: Fetch from YouTube URL
    3. RSS/Podcast mode: Fetch from iTunes search or RSS feed

    After fetching, applies podcast-specific configuration from YAML/JSON config.

    Args:
        config: Pipeline configuration dictionary (modified in place for podcast config)
        interactive_mode_meta: Pre-loaded metadata from interactive selection (or None)
        interactive_mode_wd: Pre-determined workdir from interactive selection (or None)
        progress: Progress tracker instance
        verbose: Enable verbose logging

    Returns:
        Tuple of (episode_metadata, working_directory)

    Raises:
        ValidationError: If no source (show/RSS/YouTube) is provided
        SystemExit: On fetch failures
    """
    # 1. Interactive mode: metadata and workdir already determined
    if interactive_mode_meta is not None and interactive_mode_wd is not None:
        # Check if audio file exists; if not, need to fetch
        audio_path = interactive_mode_meta.get("audio_path")
        if audio_path and Path(audio_path).exists():
            return interactive_mode_meta, interactive_mode_wd

        # Audio missing - populate config from metadata and fall through to fetch
        if interactive_mode_meta.get("show"):
            config["show"] = interactive_mode_meta["show"]
        if interactive_mode_meta.get("episode_published"):
            config["date"] = interactive_mode_meta["episode_published"]
        if interactive_mode_meta.get("episode_title"):
            config["title_contains"] = interactive_mode_meta["episode_title"]
        if interactive_mode_meta.get("feed"):
            config["rss_url"] = interactive_mode_meta["feed"]

        # Use the selected episode's workdir instead of generating a new one
        config["workdir"] = interactive_mode_wd

    # 2. YouTube URL mode
    if config.get("youtube_url"):
        from podx.cli.youtube import get_youtube_metadata, is_youtube_url

        youtube_url = config["youtube_url"]
        if not is_youtube_url(youtube_url):
            raise ValidationError(f"Invalid YouTube URL: {youtube_url}")

        progress.start_step("Fetching YouTube video metadata")

        # Get metadata first to determine workdir
        youtube_metadata = get_youtube_metadata(youtube_url)

        # Create metadata dict
        meta = {
            "show": youtube_metadata["channel"],
            "episode_title": youtube_metadata["title"],
            "episode_published": youtube_metadata.get("upload_date", ""),
        }

        progress.complete_step(
            f"YouTube metadata fetched: {meta.get('episode_title', 'Unknown')[:TITLE_MAX_LENGTH]}"
        )

        # Note: YouTube audio will be downloaded after workdir is created
        # (handled by run() function after execute_fetch returns)

    # 3. RSS/Podcast mode
    else:
        fetch_cmd = CommandBuilder("podx-fetch")
        if config.get("show"):
            fetch_cmd.add_option("--show", config["show"])
        elif config.get("rss_url"):
            fetch_cmd.add_option("--rss-url", config["rss_url"])
        else:
            raise ValidationError(
                "Either --show, --rss-url, or --youtube-url must be provided."
            )

        if config.get("date"):
            fetch_cmd.add_option("--date", config["date"])
        if config.get("title_contains"):
            fetch_cmd.add_option("--title-contains", config["title_contains"])
        if config.get("workdir"):
            fetch_cmd.add_option("--outdir", str(config["workdir"]))

        # Run fetch first to get metadata
        progress.start_step("Fetching episode metadata")
        meta = _run(
            fetch_cmd.build(),
            verbose=verbose,
            save_to=None,  # Don't save yet, we'll save after determining workdir
            label=None,  # Progress handles the display
        )
        progress.complete_step(
            f"Episode fetched: {meta.get('episode_title', 'Unknown')}"
        )

    # 4. Apply podcast-specific configuration from YAML/JSON
    from podx.utils import apply_podcast_config

    show_name = meta.get("show") or meta.get("show_name", "")

    # Current flags to potentially override
    current_flags = {
        "align": config["align"],
        "diarize": config["diarize"],
        "deepcast": config["deepcast"],
        "extract_markdown": config["extract_markdown"],
        "notion": config["notion"],
    }

    config_result = apply_podcast_config(
        show_name=show_name,
        current_flags=current_flags,
        deepcast_model=config["deepcast_model"],
        deepcast_temp=config["deepcast_temp"],
        notion=config["notion"],
        logger=logger,
    )

    # Update config with podcast-specific overrides
    config["align"] = config_result.flags["align"]
    config["diarize"] = config_result.flags["diarize"]
    config["deepcast"] = config_result.flags["deepcast"]
    config["extract_markdown"] = config_result.flags["extract_markdown"]
    config["notion"] = config_result.flags["notion"]
    config["deepcast_model"] = config_result.deepcast_model
    config["deepcast_temp"] = config_result.deepcast_temp
    config["yaml_analysis_type"] = config_result.yaml_analysis_type

    # 5. Determine working directory
    if config.get("workdir"):
        wd = config["workdir"]
    else:
        from podx.utils import generate_workdir

        show = meta.get("show", "Unknown Show")
        episode_date = meta.get("episode_published") or config.get("date") or "unknown"
        wd = generate_workdir(show, episode_date)

    return meta, wd


def execute_transcribe(
    model: str,
    compute: str,
    asr_provider: str,
    audio: dict,
    wd: Path,
    progress,
    verbose: bool,
) -> tuple[dict, str]:
    """Execute transcription step.

    Handles transcript discovery and resume support.

    Args:
        model: ASR model name (e.g., "large-v3")
        compute: Compute type (int8, float16, float32)
        asr_provider: ASR provider (auto, local, openai, hf)
        audio: Audio metadata dict from transcode step
        wd: Working directory Path
        progress: Progress tracker instance
        verbose: Enable verbose logging

    Returns:
        Tuple of (latest_transcript_dict, latest_transcript_name)
        - latest_transcript_dict: JSON data of the latest transcript
        - latest_transcript_name: Filename without .json extension

    Resume Support:
        - Reuses existing transcripts for the same model
        - Falls back to best available model if exact match not found
    """
    import json

    from podx.utils import discover_transcripts, sanitize_model_name

    existing_transcripts = discover_transcripts(wd)

    # Proposed output filename (sanitized model to avoid colons/spaces)
    transcript_file = wd / f"transcript-{sanitize_model_name(model)}.json"

    # Check legacy transcript.json
    legacy_transcript = wd / "transcript.json"
    if legacy_transcript.exists():
        try:
            legacy_data = json.loads(legacy_transcript.read_text())
            legacy_model = legacy_data.get("asr_model", "unknown")
            existing_transcripts[legacy_model] = legacy_transcript
        except Exception:
            existing_transcripts["unknown"] = legacy_transcript

    if transcript_file.exists():
        # Use existing transcript for this specific model
        logger.info(
            f"Found existing transcript for model {model}, skipping transcription"
        )
        base = json.loads(transcript_file.read_text())
        progress.complete_step(
            f"Using existing transcript ({model}) - {len(base.get('segments', []))} segments",
            0,
        )
    elif existing_transcripts:
        # Found transcripts with other models - pick the most sophisticated among known order
        order = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
        available = list(existing_transcripts.keys())
        best = None
        for m in reversed(order):
            if m in available:
                best = m
                break
        best_model = best or available[0]

        logger.info(f"Found existing transcript with model {best_model}, using it")
        base = json.loads(existing_transcripts[best_model].read_text())
        progress.complete_step(
            f"Using existing transcript ({best_model}) - {len(base.get('segments', []))} segments",
            0,
        )
    else:
        # Single track transcription
        progress.start_step(f"Transcribing with {model} model")
        step_start = time.time()
        from .services import CommandBuilder

        transcribe_cmd = (
            CommandBuilder("podx-transcribe")
            .add_option("--model", model)
            .add_option("--compute", compute)
        )
        if asr_provider and asr_provider != "auto":
            # Convert asr_provider enum to string value if needed
            asr_provider_value = (
                asr_provider.value if hasattr(asr_provider, "value") else asr_provider
            )
            transcribe_cmd.add_option("--asr-provider", asr_provider_value)

        base = _run(
            transcribe_cmd.build(),
            stdin_payload=audio,
            verbose=verbose,
            save_to=transcript_file,
            label=None,
        )
        step_duration = time.time() - step_start
        progress.complete_step(
            f"Transcription complete - {len(base.get('segments', []))} segments",
            step_duration,
        )

    # Set latest and latest_name
    latest = base
    latest_name = f"transcript-{base.get('asr_model', model)}"
    return latest, latest_name

def execute_enhancement(
    preprocess: bool,
    restore: bool,
    align: bool,
    diarize: bool,
    model: str,
    latest: dict,
    latest_name: str,
    wd: Path,
    progress,
    verbose: bool,
) -> tuple[dict, str]:
    """Execute transcript enhancement pipeline (preprocess, align, diarize).

    Processes transcripts through optional enhancement steps, updating the
    latest transcript and its name as each step completes.

    Args:
        preprocess: Enable transcript preprocessing
        restore: Enable semantic restore in preprocessing
        align: Enable word-level alignment (WhisperX)
        diarize: Enable speaker diarization
        model: ASR model name (for file naming)
        latest: Latest transcript dict (input)
        latest_name: Latest transcript filename without extension (input)
        wd: Working directory Path
        progress: Progress tracker instance
        verbose: Enable verbose logging

    Returns:
        Tuple of (enhanced_transcript_dict, enhanced_transcript_name)
        - Returns input values unchanged if no enhancement steps enabled

    Resume Support:
        - Reuses existing aligned/diarized transcripts
        - Supports legacy filename formats
    """
    import json

    from podx.utils import build_preprocess_command, sanitize_model_name

    # 4) PREPROCESS (optional)
    if preprocess:
        progress.start_step("Preprocessing transcript (merge/normalize)")
        step_start = time.time()

        # Preprocess the latest transcript
        used_model = (
            (latest or {}).get("asr_model", model)
            if isinstance(latest, dict)
            else model
        )
        pre_file = (
            wd / f"transcript-preprocessed-{sanitize_model_name(used_model)}.json"
        )
        latest = _run(
            build_preprocess_command(pre_file, restore),
            stdin_payload=latest,  # latest contains the base transcript JSON
            verbose=verbose,
            save_to=pre_file,
            label=None,
        )
        latest_name = f"transcript-preprocessed-{used_model}"

        step_duration = time.time() - step_start
        progress.complete_step("Preprocessing completed", step_duration)

    # 5) DIARIZE (optional)
    if diarize:
        # Get model from latest transcript
        used_model = latest.get("asr_model", model)
        diarized_file = (
            wd / f"transcript-diarized-{sanitize_model_name(used_model)}.json"
        )

        # Check if already exists (also check legacy filenames)
        legacy_diarized_new = wd / f"diarized-transcript-{used_model}.json"
        legacy_diarized = wd / "diarized-transcript.json"
        if diarized_file.exists():
            logger.info(
                f"Found existing diarized transcript ({used_model}), skipping diarization"
            )
            diar = json.loads(diarized_file.read_text())
            progress.complete_step(
                f"Using existing diarized transcript ({used_model})", 0
            )
            latest = diar
            latest_name = f"transcript-diarized-{used_model}"
        elif legacy_diarized_new.exists():
            logger.info(
                f"Found existing legacy diarized transcript ({used_model}), using it"
            )
            diar = json.loads(legacy_diarized_new.read_text())
            progress.complete_step("Using existing diarized transcript", 0)
            latest = diar
            latest_name = f"transcript-diarized-{used_model}"
        elif legacy_diarized.exists():
            logger.info("Found existing legacy diarized transcript, using it")
            diar = json.loads(legacy_diarized.read_text())
            progress.complete_step("Using existing diarized transcript", 0)
            latest = diar
            latest_name = "transcript-diarized"
        else:
            progress.start_step("Identifying speakers")
            step_start = time.time()
            # Debug: Check what we're passing to diarize
            if verbose:
                import click

                click.secho(
                    f"Debug: Passing {latest_name} JSON to diarize with {len(latest.get('segments', []))} segments",
                    fg="yellow",
                )
            from .services import CommandBuilder

            diarize_cmd = CommandBuilder(
                "podx-diarize"
            )  # Audio path comes from aligned transcript JSON
            diar = _run(
                diarize_cmd.build(),
                stdin_payload=latest,
                verbose=verbose,
                save_to=diarized_file,
                label=None,  # Progress handles the display
            )
            step_duration = time.time() - step_start
            progress.complete_step("Speaker diarization completed", step_duration)
            latest = diar
            latest_name = f"transcript-diarized-{used_model}"

    return latest, latest_name

def execute_deepcast(
    deepcast: bool,
    model: str,
    deepcast_model: str,
    deepcast_temp: float,
    yaml_analysis_type: Optional[str],
    extract_markdown: bool,
    deepcast_pdf: bool,
    wd: Path,
    results: dict,
    progress,
    verbose: bool,
) -> None:
    """Execute deepcast analysis step.

    Handles AI-powered transcript analysis.

    Args:
        deepcast: Enable deepcast analysis
        model: ASR model name (for file naming)
        deepcast_model: AI model for deepcast analysis
        deepcast_temp: Temperature for deepcast LLM calls
        yaml_analysis_type: Optional analysis type from YAML config
        extract_markdown: Extract markdown from deepcast output
        deepcast_pdf: Generate PDF from deepcast output
        wd: Working directory Path
        results: Results dictionary (modified in place)
        progress: Progress tracker instance
        verbose: Enable verbose logging

    Side Effects:
        - Updates results dict with deepcast output paths
        - Creates deepcast JSON/MD files in working directory

    Resume Support:
        - Reuses existing deepcast analysis if available
    """

    from podx.utils import build_deepcast_command

    if not deepcast:
        return

    # Use model-specific filenames to allow multiple analyses
    model_suffix = deepcast_model.replace(".", "_").replace("-", "_")
    json_out = wd / f"deepcast-{model_suffix}.json"
    md_out = wd / f"deepcast-{model_suffix}.md"

    if json_out.exists():
        logger.info("Found existing deepcast analysis, skipping AI analysis")
        progress.complete_step("Using existing AI analysis", 0)
        results.update({"deepcast_json": str(json_out)})
        if extract_markdown and md_out.exists():
            results.update({"deepcast_md": str(md_out)})
    else:
        # Single-track deepcast always reads the latest processed transcript
        progress.start_step(f"Analyzing transcript with {deepcast_model}")
        step_start = time.time()
        latest_path = wd / "latest.json"
        meta_file = wd / "episode-meta.json"

        cmd = build_deepcast_command(
            input_path=latest_path,
            output_path=json_out,
            model=deepcast_model,
            temperature=deepcast_temp,
            meta_path=meta_file,
            analysis_type=yaml_analysis_type,
            extract_markdown=extract_markdown,
            generate_pdf=deepcast_pdf,
        )
        _run(cmd, verbose=verbose, save_to=None, label=None)
        step_duration = time.time() - step_start
        progress.complete_step("AI analysis completed", step_duration)
        results.update({"deepcast_json": str(json_out)})
        if extract_markdown and md_out.exists():
            results.update({"deepcast_md": str(md_out)})

def execute_notion_upload(
    notion_db: str,
    wd: Path,
    results: dict,
    deepcast_model: str,
    model: str,
    podcast_prop: str,
    date_prop: str,
    episode_prop: str,
    model_prop: str,
    asr_prop: str,
    append_content: bool,
    progress,
    verbose: bool,
) -> None:
    """Execute Notion page creation/update with deepcast content.

    Uploads transcript analysis to Notion database, preferring exported markdown
    when available, falling back to model-specific deepcast files, and using
    JSON-only mode when no markdown exists.

    Args:
        notion_db: Notion database ID or key from YAML config
        wd: Working directory Path
        results: Results dictionary containing output file paths
        deepcast_model: AI model used for deepcast analysis
        model: ASR model name
        podcast_prop: Notion property name for podcast
        date_prop: Notion property name for date
        episode_prop: Notion property name for episode
        model_prop: Notion property name for model
        asr_prop: Notion property name for ASR provider
        append_content: Append to existing page instead of replacing
        progress: Progress tracker instance
        verbose: Enable verbose logging

    Side Effects:
        - Creates/updates Notion page
        - Saves notion.out.json to working directory
        - Updates results dict with notion output path
    """

    progress.start_step("Uploading to Notion")
    step_start = time.time()

    from .services import CommandBuilder

    # Prefer exported.md if available, else model-specific deepcast outputs, fallback to latest.txt
    model_suffix = deepcast_model.replace(".", "_").replace("-", "_")
    exported_md = (
        Path(results.get("exported_md", "")) if results.get("exported_md") else None
    )
    model_specific_md = wd / f"deepcast-{model_suffix}.md"
    model_specific_json = wd / f"deepcast-{model_suffix}.json"

    # Build command using CommandBuilder
    cmd = CommandBuilder("podx-notion")

    # If exported exists, use it directly
    if exported_md and exported_md.exists():
        md_path = str(exported_md)
        json_path = str(model_specific_json) if model_specific_json.exists() else None
        cmd.add_option("--markdown", md_path)
        cmd.add_option("--meta", str(wd / "episode-meta.json"))
        if json_path:
            cmd.add_option("--json", json_path)
    else:
        # Find any deepcast files if model-specific ones don't exist
        # Check for both new and legacy formats
        deepcast_files = list(wd.glob("deepcast-*.md"))
        fallback_md = deepcast_files[0] if deepcast_files else None

        # Prefer unified JSON mode if no separate markdown file exists
        if model_specific_json.exists() and not model_specific_md.exists():
            # Use unified JSON mode (deepcast JSON contains markdown)
            cmd.add_option("--input", str(model_specific_json))
        else:
            # Use separate markdown + JSON mode
            md_path = (
                str(model_specific_md)
                if model_specific_md.exists()
                else str(fallback_md) if fallback_md else str(wd / "latest.txt")
            )
            json_path = (
                str(model_specific_json) if model_specific_json.exists() else None
            )

            cmd.add_option("--markdown", md_path)
            cmd.add_option("--meta", str(wd / "episode-meta.json"))
            if json_path:
                cmd.add_option("--json", json_path)

    # Add common options
    cmd.add_option("--db", notion_db)
    cmd.add_option("--podcast-prop", podcast_prop)
    cmd.add_option("--date-prop", date_prop)
    cmd.add_option("--episode-prop", episode_prop)
    cmd.add_option("--model-prop", model_prop)
    cmd.add_option("--asr-prop", asr_prop)
    cmd.add_option("--deepcast-model", deepcast_model)
    cmd.add_option("--asr-model", model)  # The ASR model from transcription

    if append_content:
        cmd.add_flag("--append-content")
    # Default is replace, so no flag needed when append_content is False

    _ = _run(
        cmd.build(),
        verbose=verbose,
        save_to=wd / "notion.out.json",
        label=None,  # Progress handles the display
    )
    step_duration = time.time() - step_start
    progress.complete_step("Notion page created/updated", step_duration)
    results.update({"notion": str(wd / "notion.out.json")})

def execute_cleanup(
    clean: bool,
    no_keep_audio: bool,
    wd: Path,
    latest_name: str,
    transcoded_path: Path,
    original_audio_path: Path | None,
    progress,
) -> None:
    """Execute optional file cleanup after pipeline completion.

    Removes intermediate transcript files and optionally audio files,
    while preserving final artifacts like latest.json, exported files,
    and deepcast outputs.

    Args:
        clean: Enable cleanup of intermediate files
        no_keep_audio: Also remove audio files
        wd: Working directory Path
        latest_name: Name of the latest transcript (without extension)
        transcoded_path: Path to transcoded audio file
        original_audio_path: Path to original audio file (may be None)
        progress: Progress tracker instance

    Side Effects:
        - Deletes intermediate transcript JSON files
        - Optionally deletes audio files
        - Logs cleanup actions
    """

    if not clean:
        return

    progress.start_step("Cleaning up intermediate files")
    step_start = time.time()

    # Keep final artifacts (small pointers)
    keep = {
        wd / "latest.json",
        wd / f"{latest_name}.txt",
        wd / f"{latest_name}.srt",
        wd / "notion.out.json",
        wd / "episode-meta.json",
        wd / "audio-meta.json",
    }
    # Keep all deepcast files (both new and legacy formats)
    keep.update(wd.glob("deepcast-*.json"))
    keep.update(wd.glob("deepcast-*.md"))

    cleaned_files = 0

    # Remove intermediate JSON files (both legacy and model-specific)
    cleanup_patterns = [
        "transcript.json",
        "transcript-*.json",
        # Legacy align/diarize formats (old)
        "aligned-transcript.json",
        "aligned-transcript-*.json",
        "diarized-transcript.json",
        "diarized-transcript-*.json",
        # New align/diarize formats
        "transcript-aligned.json",
        "transcript-aligned-*.json",
        "transcript-diarized.json",
        "transcript-diarized-*.json",
    ]
    for pattern in cleanup_patterns:
        for p in wd.glob(pattern):
            if p.exists() and p not in keep:
                try:
                    p.unlink()
                    cleaned_files += 1
                    logger.debug("Cleaned intermediate file", file=str(p))
                except Exception as e:
                    logger.warning("Failed to clean file", file=str(p), error=str(e))

    # Remove audio files if not keeping them
    if no_keep_audio:
        for p in [transcoded_path, original_audio_path]:
            if p and p.exists():
                try:
                    p.unlink()
                    cleaned_files += 1
                    logger.debug("Cleaned audio file", file=str(p))
                except Exception as e:
                    logger.warning(
                        "Failed to clean audio file", file=str(p), error=str(e)
                    )

    step_duration = time.time() - step_start
    progress.complete_step(
        f"Cleanup completed ({cleaned_files} files removed)", step_duration
    )

def print_results_summary(
    start_time: float,
    steps: list[str],
    wd: Path,
    results: dict,
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
    import json

    from .progress import format_duration, print_podx_info, print_podx_success

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

def display_pipeline_config(
    align: bool,
    diarize: bool,
    deepcast: bool,
    notion: bool,
    show: str | None,
    rss_url: str | None,
    date: str | None,
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
    from .progress import print_podx_info

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

def execute_export_formats(
    latest: dict,
    latest_name: str,
    wd: Path,
    progress,
    verbose: bool,
) -> dict:
    """Execute transcript export to TXT/SRT formats and build results dictionary.

    Exports the latest transcript to text and subtitle formats, then constructs
    the results dictionary with paths to all generated files.

    Args:
        latest: Latest transcript dictionary
        latest_name: Name of the latest transcript file (without extension)
        wd: Working directory path
        progress: Progress tracker
        verbose: Enable verbose logging

    Returns:
        Dictionary with paths to generated files (meta, audio, transcript, txt, srt)
    """

    from .services import CommandBuilder

    # Export to TXT/SRT formats
    progress.start_step("Exporting transcript files")
    step_start = time.time()

    export_cmd = (
        CommandBuilder("podx-export")
        .add_option("--formats", "txt,srt")
        .add_option("--output-dir", str(wd))
        .add_option("--input", str(wd / f"{latest_name}.json"))
        .add_flag("--replace")
    )
    export_result = _run(
        export_cmd.build(),
        stdin_payload=latest,
        verbose=verbose,
        label=None,  # Progress handles the display
    )
    step_duration = time.time() - step_start
    progress.complete_step("Transcript files exported (TXT, SRT)", step_duration)

    # Build results using export output paths when available
    exported_files = (
        export_result.get("files", {}) if isinstance(export_result, dict) else {}
    )
    results = {
        "meta": str(wd / "episode-meta.json"),
        "audio": str(wd / "audio-meta.json"),
        "transcript": str(wd / f"{latest_name}.json"),
        "latest_json": str(wd / "latest.json"),
    }
    if "txt" in exported_files:
        results["latest_txt"] = exported_files["txt"]
    else:
        results["latest_txt"] = str(wd / f"{latest_name}.txt")
    if "srt" in exported_files:
        results["latest_srt"] = exported_files["srt"]
    else:
        results["latest_srt"] = str(wd / f"{latest_name}.srt")

    return results

def execute_export_final(
    preset: str | None,
    deepcast_pdf: bool,
    wd: Path,
    results: dict,
) -> None:
    """Execute final export of deepcast analysis to markdown/PDF.

    Exports deepcast output to timestamped markdown and optionally PDF files.

    Args:
        preset: ASR preset used (for track naming)
        deepcast_pdf: Generate PDF output
        wd: Working directory Path
        results: Results dictionary (modified in place with exported paths)

    Side Effects:
        - Exports markdown to wd/exported-<timestamp>.md
        - Optionally exports PDF to wd/exported-<timestamp>.pdf
        - Updates results dict with exported_md and exported_pdf keys
    """

    from .export import export_from_deepcast_json

    # Final export step (write exported-<timestamp>.* from deepcast output)
    try:
        single = results.get("deepcast_json")
        if single and Path(single).exists():
            export_source_path = Path(single)
            export_track = (preset or "balanced") if preset else "single"

            data = json.loads(export_source_path.read_text(encoding=DEFAULT_ENCODING))
            # Use unified exporter (handles deepcast JSON, and PDF auto-install)
            try:
                md_path, pdf_path = export_from_deepcast_json(
                    data, wd, deepcast_pdf, track_hint=export_track
                )
                results["exported_md"] = str(md_path)
                if pdf_path is not None:
                    results["exported_pdf"] = str(pdf_path)
            except Exception:
                pass
    except Exception:
        pass

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
                import json

                transcript_json = json.loads(
                    latest_path.read_text(encoding=DEFAULT_ENCODING)
                )
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
                import subprocess

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
        processing_parts.append(
            f"{num_transcripts} transcript{'s' if num_transcripts > 1 else ''}"
        )
    if num_aligned > 0:
        processing_parts.append(f"{num_aligned} aligned")
    if num_diarized > 0:
        processing_parts.append(f"{num_diarized} diarized")
    if num_deepcasts > 0:
        processing_parts.append(
            f"{num_deepcasts} deepcast{'s' if num_deepcasts > 1 else ''}"
        )
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
            from .deepcast import estimate_deepcast_cost
            from .model_catalog import load_model_catalog

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

def handle_interactive_mode(
    config: Dict[str, Any], scan_dir: Path, console: Any
) -> tuple[Dict[str, Any], Path]:
    """Handle interactive episode selection and configuration.

    Displays rich table UI for episode selection and interactive
    configuration panel. Modifies config dict in place.

    Args:
        config: Pipeline configuration dictionary (modified in place)
        scan_dir: Directory to scan for episodes
        console: Rich console instance

    Returns:
        Tuple of (episode_metadata, working_directory)

    Raises:
        SystemExit: If user cancels selection
    """

    from podx.ui import select_episode_with_tui

    # 1. Episode selection
    selected, meta = select_episode_with_tui(
        scan_dir=scan_dir,
        show_filter=config["show"],
    )

    # 2. Interactive configuration panel
    from podx.ui import configure_pipeline_interactive

    updated_config = configure_pipeline_interactive(config)
    if updated_config is None:
        console.print("[dim]Cancelled[/dim]")
        raise SystemExit(0)

    # Merge updated config back
    config.update(updated_config)
    chosen_type = config.get("yaml_analysis_type")

    # 6. Episode metadata display
    episode_metadata = build_episode_metadata_display(selected, meta, config)
    console.print(Panel(episode_metadata, title="Episode", border_style="cyan"))

    # 7. Pipeline preview
    stages = ["fetch", "transcode", "transcribe"]
    if config["align"]:
        stages.append("align")
    if config["diarize"]:
        stages.append("diarize")
    if config["preprocess"]:
        stages.append("preprocess" + ("+restore" if config["restore"] else ""))
    if config["deepcast"]:
        stages.append("deepcast")

    outputs = []
    if config["extract_markdown"]:
        outputs.append("markdown")
    if config["deepcast_pdf"]:
        outputs.append("pdf")

    def yn(val: bool) -> str:
        return "yes" if val else "no"

    preview = (
        f"Pipeline: {' → '.join(stages)}\n"
        f"ASR={config['model']} "
        f"align={yn(config['align'])} diarize={yn(config['diarize'])} "
        f"preprocess={yn(config['preprocess'])} restore={yn(config['restore'])}\n"
        f"AI={config['deepcast_model']} type={chosen_type or '-'} outputs={','.join(outputs) or '-'}"
    )

    console.print(Panel(preview, title="Pipeline", border_style="green"))

    # 7. Final confirmation (strict y/n validation)
    while True:
        cont = input("Proceed? (y/n; q cancel) [Y]: ").strip()
        if not cont:
            break
        c = cont.lower()
        if c in {"q", "quit", "exit"}:
            console.print("[dim]Cancelled[/dim]")
            raise SystemExit(0)
        if c in {"y", "n"}:
            if c == "n":
                console.print("[dim]Cancelled[/dim]")
                raise SystemExit(0)
            break
        print("Please enter 'y' or 'n' (or 'q' to cancel).")

    # Update config with chosen analysis type
    config["yaml_analysis_type"] = chosen_type

    # Return metadata and working directory
    workdir = selected["directory"]
    return meta, workdir
