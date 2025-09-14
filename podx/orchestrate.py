#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

import click

# Import individual command modules for CLI integration
from . import (
    align,
    browse,
    deepcast,
    diarize,
    export,
    fetch,
    notion,
    transcode,
    transcribe,
)
from .config import get_config
from .errors import ValidationError
from .fetch import _generate_workdir
from .help import help_cmd
from .logging import get_logger, setup_logging
from .plugins import PluginManager, PluginType, get_registry
from .podcast_config import (
    PREDEFINED_CONFIGS,
    PodcastAnalysisConfig,
    create_predefined_configs,
    get_podcast_config,
    get_podcast_config_manager,
)
from .progress import (
    PodxProgress,
    format_duration,
    print_podx_header,
    print_podx_info,
    print_podx_success,
)
from .prompt_templates import PodcastType
from .yaml_config import (
    NotionDatabase,
    PodcastMapping,
    get_notion_database_config,
    get_podcast_yaml_config,
    get_yaml_config_manager,
    load_yaml_config,
)

# Initialize logging
setup_logging()
logger = get_logger(__name__)


def _run(
    cmd: List[str],
    stdin_payload: Dict | None = None,
    verbose: bool = False,
    save_to: Path | None = None,
    label: str | None = None,
) -> Dict:
    """Run a CLI tool that prints JSON to stdout; return parsed dict."""
    if label:
        logger.debug("Running command", command=" ".join(cmd), label=label)

    proc = subprocess.run(
        cmd,
        input=json.dumps(stdin_payload) if stdin_payload else None,
        text=True,
        capture_output=True,
    )

    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        logger.error(
            "Command failed",
            command=" ".join(cmd),
            return_code=proc.returncode,
            error=err,
        )
        raise ValidationError(f"Command failed: {' '.join(cmd)}\n{err}")

    # stdout should be JSON; optionally mirror to console
    out = proc.stdout

    if verbose:
        # Show a compact preview of the JSON output
        preview = out[:400] + "..." if len(out) > 400 else out
        click.secho(preview, fg="white")

    try:
        data = json.loads(out)
        logger.debug("Command completed successfully", command=cmd[0])
    except json.JSONDecodeError:
        # Some subcommands (e.g., deepcast/notion) print plain text "Wrote: ..."
        data = {"stdout": out.strip()}
        logger.debug("Command returned non-JSON output", command=cmd[0])

    if save_to:
        save_to.write_text(out, encoding="utf-8")
        logger.debug("Output saved", file=str(save_to))

    return data


@click.group()
def main():
    """Podx: Composable podcast processing pipeline

    A modular toolkit for podcast transcription, analysis, and publishing.

    WORKFLOWS:
      run       Complete customizable pipeline
      quick     Fast transcription only (fetch + transcribe)
      analyze   AI analysis workflow (transcribe + align + deepcast)
      publish   Full pipeline with Notion upload

    STAGES:
      fetch, transcode, transcribe, align, diarize, export, deepcast, notion

    UTILITIES:
      help, list, config, plugin

    Use 'podx list' to see all commands or 'podx help --examples' for usage examples.
    Use 'podx plugin list' to see available plugins.
    """
    pass


@main.command("run", help="Orchestrate the complete podcast processing pipeline.")
@click.option("--show", help="Podcast show name (iTunes search)")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
@click.option("--date", help="Episode date (YYYY-MM-DD)")
@click.option("--title-contains", help="Substring to match in episode title")
@click.option(
    "--workdir",
    type=click.Path(path_type=Path),
    help="Override working directory (bypasses smart naming)",
)
@click.option(
    "--fmt",
    default="wav16",
    type=click.Choice(["wav16", "mp3", "aac"]),
    help="Transcode format for ASR step [default: wav16]",
)
@click.option(
    "--model",
    default=lambda: get_config().default_asr_model,
    help="ASR transcription model",
)
@click.option(
    "--compute",
    default=lambda: get_config().default_compute,
    type=click.Choice(["int8", "int8_float16", "float16", "float32"]),
    help="Compute type",
)
@click.option(
    "--align",
    is_flag=True,
    help="Run WhisperX alignment (default: no alignment)",
)
@click.option(
    "--diarize",
    is_flag=True,
    help="Run diarization (default: no diarization)",
)
@click.option(
    "--deepcast",
    is_flag=True,
    help="Run LLM summarization (default: no AI analysis)",
)
@click.option(
    "--deepcast-model",
    default=lambda: get_config().openai_model,
    help="OpenAI model for AI analysis",
)
@click.option(
    "--deepcast-temp",
    default=lambda: get_config().openai_temperature,
    type=float,
    help="OpenAI temperature for deepcast",
)
@click.option(
    "--extract-markdown",
    is_flag=True,
    help="Also extract raw markdown file when running deepcast",
)
@click.option(
    "--notion",
    is_flag=True,
    help="Upload to Notion database (default: no upload)",
)
@click.option(
    "--db",
    "notion_db",
    default=lambda: get_config().notion_db_id,
    help="Notion database ID (required if --notion)",
)
@click.option(
    "--podcast-prop",
    default=lambda: get_config().notion_podcast_prop,
    help="Notion property name for podcast name",
)
@click.option(
    "--date-prop",
    default=lambda: get_config().notion_date_prop,
    help="Notion property name for date",
)
@click.option(
    "--episode-prop",
    default=lambda: get_config().notion_episode_prop,
    help="Notion property name for episode title",
)
@click.option(
    "--append-content",
    is_flag=True,
    help="Append to page body in Notion instead of replacing (default: replace)",
)
@click.option(
    "--full",
    is_flag=True,
    help="Enable full pipeline: --align --deepcast --extract-markdown --notion (convenience flag)",
)
@click.option("-v", "--verbose", is_flag=True, help="Print interstitial outputs")
@click.option(
    "--clean",
    is_flag=True,
    help="Delete intermediates after success (default: keep all files)",
)
@click.option(
    "--no-keep-audio",
    is_flag=True,
    help="Delete audio files when --clean is used (default: keep audio)",
)
def run(
    show: Optional[str],
    rss_url: Optional[str],
    date: Optional[str],
    title_contains: Optional[str],
    workdir: Optional[Path],
    fmt: str,
    model: str,
    compute: str,
    align: bool,
    diarize: bool,
    deepcast: bool,
    deepcast_model: str,
    deepcast_temp: float,
    extract_markdown: bool,
    notion: bool,
    notion_db: Optional[str],
    podcast_prop: str,
    date_prop: str,
    episode_prop: str,
    append_content: bool,
    full: bool,
    verbose: bool,
    clean: bool,
    no_keep_audio: bool,
):
    """Orchestrate the complete podcast processing pipeline."""
    # Handle convenience --full flag
    if full:
        align = True
        deepcast = True
        extract_markdown = True
        notion = True

    # Print header and start progress tracking
    print_podx_header()

    start_time = time.time()

    # Initialize results dictionary
    results = {}

    # Use progress tracking for the entire pipeline
    with PodxProgress() as progress:
        # We'll determine the actual workdir after fetching metadata
        wd = None  # Will be set after fetch

        # 1) FETCH → meta.json
        fetch_cmd = ["podx-fetch"]
        if show:
            fetch_cmd.extend(["--show", show])
        elif rss_url:
            fetch_cmd.extend(["--rss-url", rss_url])
        else:
            raise ValidationError("Either --show or --rss-url must be provided.")

        if date:
            fetch_cmd.extend(["--date", date])
        if title_contains:
            fetch_cmd.extend(["--title-contains", title_contains])

        # Run fetch first to get metadata, then determine workdir
        progress.start_step("Fetching episode metadata")
        meta = _run(
            fetch_cmd,
            verbose=verbose,
            save_to=None,  # Don't save yet, we'll save after determining workdir
            label=None,  # Progress handles the display
        )
        progress.complete_step(
            f"Episode fetched: {meta.get('episode_title', 'Unknown')}"
        )

        # Check for podcast-specific configuration after we have the show name
        show_name = meta.get("show") or meta.get("show_name", "")

        # Try YAML config first, then fall back to JSON config
        yaml_config = get_podcast_yaml_config(show_name) if show_name else None
        json_config = get_podcast_config(show_name) if show_name else None

        # Apply podcast-specific defaults (YAML takes precedence over JSON)
        active_config = yaml_config or json_config
        config_type = "YAML" if yaml_config else "JSON" if json_config else None
        yaml_analysis_type = None  # Initialize for later use

        if active_config:
            # Determine config type and extract settings
            if yaml_config:
                logger.info(
                    "Found YAML podcast configuration",
                    show=show_name,
                    config_type=config_type,
                )

                # Apply YAML pipeline defaults
                if yaml_config.pipeline:
                    if not align and yaml_config.pipeline.align:
                        align = True
                        logger.info("Applied YAML config: align = True")
                    if not diarize and yaml_config.pipeline.diarize:
                        diarize = True
                        logger.info("Applied YAML config: diarize = True")
                    if not deepcast and yaml_config.pipeline.deepcast:
                        deepcast = True
                        logger.info("Applied YAML config: deepcast = True")
                    if not extract_markdown and yaml_config.pipeline.extract_markdown:
                        extract_markdown = True
                        logger.info("Applied YAML config: extract_markdown = True")
                    if not notion and yaml_config.pipeline.notion:
                        notion = True
                        logger.info("Applied YAML config: notion = True")

                # Apply YAML analysis settings
                if yaml_config.analysis:
                    base_config = get_config()
                    if (
                        deepcast_model == base_config.openai_model
                        and yaml_config.analysis.model
                    ):
                        deepcast_model = yaml_config.analysis.model
                        logger.info("Applied YAML config model", model=deepcast_model)
                    if (
                        abs(deepcast_temp - base_config.openai_temperature) < 0.001
                        and yaml_config.analysis.temperature
                    ):
                        deepcast_temp = yaml_config.analysis.temperature
                        logger.info(
                            "Applied YAML config temperature", temperature=deepcast_temp
                        )
                    # Store analysis type for later use in deepcast
                    if yaml_config.analysis.type:
                        yaml_analysis_type = yaml_config.analysis.type.value
                        logger.info(
                            "Applied YAML config analysis type", type=yaml_analysis_type
                        )

                # Handle Notion database selection
                if yaml_config.notion_database and notion:
                    notion_db_config = get_notion_database_config(
                        yaml_config.notion_database
                    )
                    if notion_db_config:
                        notion_db = notion_db_config.database_id
                        logger.info(
                            "Applied YAML Notion database",
                            database=yaml_config.notion_database,
                        )
                        # Could also set environment variables for the token
                        import os

                        os.environ["NOTION_TOKEN"] = notion_db_config.token
                        os.environ["NOTION_PODCAST_PROP"] = (
                            notion_db_config.podcast_property
                        )
                        os.environ["NOTION_DATE_PROP"] = notion_db_config.date_property
                        os.environ["NOTION_EPISODE_PROP"] = (
                            notion_db_config.episode_property
                        )

            elif json_config:
                logger.info(
                    "Found JSON podcast configuration",
                    show=show_name,
                    config_type=json_config.podcast_type.value,
                )

                # Apply JSON defaults (original logic)
                config_flags = json_config.default_flags

                if not align and config_flags.get("align", False):
                    align = True
                    logger.info("Applied JSON config: align = True")
                if not diarize and config_flags.get("diarize", False):
                    diarize = True
                    logger.info("Applied JSON config: diarize = True")
                if not deepcast and config_flags.get("deepcast", False):
                    deepcast = True
                    logger.info("Applied JSON config: deepcast = True")
                if not extract_markdown and (
                    config_flags.get("extract_markdown", False)
                    or json_config.extract_markdown
                ):
                    extract_markdown = True
                    logger.info("Applied JSON config: extract_markdown = True")
                if not notion and (
                    config_flags.get("notion", False) or json_config.notion_upload
                ):
                    notion = True
                    logger.info("Applied JSON config: notion = True")

                # Apply model preferences
                base_config = get_config()
                if (
                    deepcast_model == base_config.openai_model
                    and json_config.deepcast_model
                ):
                    deepcast_model = json_config.deepcast_model
                    logger.info("Applied JSON config model", model=deepcast_model)
                if (
                    abs(deepcast_temp - base_config.openai_temperature) < 0.001
                    and json_config.temperature
                ):
                    deepcast_temp = json_config.temperature
                    logger.info(
                        "Applied JSON config temperature", temperature=deepcast_temp
                    )

        # Show pipeline configuration (after YAML/JSON config is applied)
        steps = ["fetch", "transcode", "transcribe"]
        if align:
            steps.append("align")
        if diarize:
            steps.append("diarize")
        steps.extend(["export"])
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

        # Determine workdir from metadata
        if workdir:
            # Override: use specified workdir
            wd = Path(workdir)
            logger.debug("Using specified workdir", workdir=str(workdir))
        else:
            # Default: use smart naming with spaces
            show_name = meta.get("show", "Unknown Show")
            episode_date = meta.get("episode_published") or date or "unknown"
            wd = _generate_workdir(show_name, episode_date)
            logger.debug("Using smart workdir", workdir=str(wd))

        wd.mkdir(parents=True, exist_ok=True)
        # Save metadata to the determined workdir
        (wd / "episode-meta.json").write_text(json.dumps(meta, indent=2))

        # Track original audio path for cleanup
        original_audio_path = Path(meta["audio_path"]) if "audio_path" in meta else None

        # 2) TRANSCODE → audio-meta.json
        audio_meta_file = wd / "audio-meta.json"
        if audio_meta_file.exists():
            logger.info("Found existing audio metadata, skipping transcode")
            audio = json.loads(audio_meta_file.read_text())
            progress.complete_step(f"Using existing {fmt} audio", 0)
        else:
            progress.start_step(f"Transcoding audio to {fmt}")
            step_start = time.time()
            audio = _run(
                ["podx-transcode", "--to", fmt, "--outdir", str(wd)],
                stdin_payload=meta,
                verbose=verbose,
                save_to=audio_meta_file,
                label=None,  # Progress handles the display
            )
            step_duration = time.time() - step_start
            progress.complete_step(f"Audio transcoded to {fmt}", step_duration)

        # Track transcoded audio path for cleanup
        transcoded_path = Path(audio["audio_path"])

        # 3) TRANSCRIBE → transcript.json
        transcript_file = wd / "transcript.json"
        if transcript_file.exists():
            logger.info("Found existing transcript, skipping transcription")
            base = json.loads(transcript_file.read_text())
            progress.complete_step(
                f"Using existing transcript - {len(base.get('segments', []))} segments",
                0,
            )
        else:
            progress.start_step(f"Transcribing with {model} model")
            step_start = time.time()
            base = _run(
                ["podx-transcribe", "--model", model, "--compute", compute],
                stdin_payload=audio,
                verbose=verbose,
                save_to=transcript_file,
                label=None,  # Progress handles the display
            )
            step_duration = time.time() - step_start
            progress.complete_step(
                f"Transcription complete - {len(base.get('segments', []))} segments",
                step_duration,
            )

        latest = base
        latest_name = "transcript"

        # 4) ALIGN (optional) → aligned-transcript.json
        if align:
            aligned_file = wd / "aligned-transcript.json"
            if aligned_file.exists():
                logger.info("Found existing aligned transcript, skipping alignment")
                aligned = json.loads(aligned_file.read_text())
                progress.complete_step("Using existing aligned transcript", 0)
                latest = aligned
                latest_name = "aligned-transcript"
            else:
                progress.start_step("Aligning transcript with audio")
                step_start = time.time()
                aligned = _run(
                    ["podx-align", "--audio", audio["audio_path"]],
                    stdin_payload=base,
                    verbose=verbose,
                    save_to=aligned_file,
                    label=None,  # Progress handles the display
                )
                step_duration = time.time() - step_start
                progress.complete_step("Audio alignment completed", step_duration)
                latest = aligned
                latest_name = "aligned-transcript"

        # 5) DIARIZE (optional) → diarized-transcript.json
        if diarize:
            progress.start_step("Identifying speakers")
            step_start = time.time()
            # Debug: Check what we're passing to diarize
            if verbose:
                click.secho(
                    f"Debug: Passing {latest_name} JSON to diarize with {len(latest.get('segments', []))} segments",
                    fg="yellow",
                )
            diar = _run(
                ["podx-diarize", "--audio", audio["audio_path"]],
                stdin_payload=latest,
                verbose=verbose,
                save_to=wd / "diarized-transcript.json",
                label=None,  # Progress handles the display
            )
            step_duration = time.time() - step_start
            progress.complete_step("Speaker diarization completed", step_duration)
            latest = diar
            latest_name = "diarized-transcript"

        # Always keep a pointer to the latest JSON/SRT/TXT for convenience
        (wd / "latest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")

        # quick TXT/SRT from whatever we have
        progress.start_step("Exporting transcript files")
        step_start = time.time()
        export_result = _run(
            [
                "podx-export",
                "--formats",
                "txt,srt",
                "--output-dir",
                str(wd),
                "--input",
                str(wd / f"{latest_name}.json"),
                "--replace",
            ],
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

        # 6) DEEPCAST (optional) → deepcast-brief.md / deepcast-brief.json
        if deepcast:
            json_out = wd / "deepcast-brief.json"
            md_out = wd / "deepcast-brief.md"

            if json_out.exists():
                logger.info("Found existing deepcast analysis, skipping AI analysis")
                progress.complete_step("Using existing AI analysis", 0)
                results.update({"deepcast_json": str(json_out)})
                if extract_markdown and md_out.exists():
                    results.update({"deepcast_md": str(md_out)})
            else:
                progress.start_step(f"Analyzing transcript with {deepcast_model}")
                step_start = time.time()
                inp = str(wd / "latest.json")
                meta_file = wd / "episode-meta.json"

                cmd = [
                    "podx-deepcast",
                    "--input",
                    inp,
                    "--output",
                    str(json_out),
                    "--model",
                    deepcast_model,
                    "--temperature",
                    str(deepcast_temp),
                ]

                # Add metadata file if it exists to fix "Unknown Show" issue
                if meta_file.exists():
                    cmd.extend(["--meta", str(meta_file)])

                # Add analysis type if configured in YAML
                if yaml_analysis_type:
                    cmd.extend(["--type", yaml_analysis_type])

                if extract_markdown:
                    cmd.append("--extract-markdown")

                _run(
                    cmd, verbose=verbose, save_to=None, label=None
                )  # Progress handles the display
                step_duration = time.time() - step_start
                progress.complete_step("AI analysis completed", step_duration)
                results.update({"deepcast_json": str(json_out)})
                # Record markdown path when extracted
                if extract_markdown and md_out.exists():
                    results.update({"deepcast_md": str(md_out)})

        # 7) NOTION (optional) — requires DB id
        if notion:
            if not notion_db:
                raise SystemExit(
                    "Please pass --db or set NOTION_DB_ID environment variable"
                )

            progress.start_step("Uploading to Notion")
            step_start = time.time()
            # Prefer brief.md from deepcast, fallback to latest.txt
            # Prefer deepcast outputs; fallback to latest.txt
            md_path = (
                str(wd / "deepcast-brief.md")
                if (wd / "deepcast-brief.md").exists()
                else str(wd / "latest.txt")
            )
            json_path = (
                str(wd / "deepcast-brief.json")
                if (wd / "deepcast-brief.json").exists()
                else None
            )

            cmd = [
                "podx-notion",
                "--markdown",
                md_path,
                "--meta",
                str(wd / "episode-meta.json"),
                "--db",
                notion_db,
                "--podcast-prop",
                podcast_prop,
                "--date-prop",
                date_prop,
                "--episode-prop",
                episode_prop,
            ]

            if json_path:
                cmd += ["--json", json_path]

            if append_content:
                cmd += ["--append-content"]
            # Default is replace, so no flag needed when append_content is False

            notion_resp = _run(
                cmd,
                verbose=verbose,
                save_to=wd / "notion.out.json",
                label=None,  # Progress handles the display
            )
            step_duration = time.time() - step_start
            progress.complete_step("Notion page created/updated", step_duration)
            results.update({"notion": str(wd / "notion.out.json")})

        # 8) Optional cleanup
        if clean:
            progress.start_step("Cleaning up intermediate files")
            step_start = time.time()
            # Keep final artifacts (small pointers)
            keep = {
                wd / "latest.json",
                wd / f"{latest_name}.txt",
                wd / f"{latest_name}.srt",
                wd / "deepcast-brief.md",
                wd / "deepcast-brief.json",
                wd / "notion.out.json",
                wd / "episode-meta.json",
                wd / "audio-meta.json",
            }

            cleaned_files = 0
            # Remove intermediate JSON files
            for p in [
                wd / "transcript.json",
                wd / "aligned-transcript.json",
                wd / "diarized-transcript.json",
            ]:
                if p.exists() and p not in keep:
                    try:
                        p.unlink()
                        cleaned_files += 1
                        logger.debug("Cleaned intermediate file", file=str(p))
                    except Exception as e:
                        logger.warning(
                            "Failed to clean file", file=str(p), error=str(e)
                        )

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
    print(json.dumps(results, indent=2))


# Add individual commands as subcommands to main CLI group
# This provides a consistent interface: podx <command> instead of podx-<command>


@main.command("browse")
@click.pass_context
def browse_cmd(ctx):
    """Interactive episode browser for podcast discovery and selection."""
    # Pass through to the browse.main() with sys.argv adjustments
    import sys

    # Remove 'podx browse' from sys.argv and call browse.main()
    original_argv = sys.argv.copy()
    sys.argv = ["podx-browse"] + sys.argv[2:]  # Keep original args after 'browse'
    try:
        browse.main()
    finally:
        sys.argv = original_argv


@main.command("fetch")
@click.pass_context
def fetch_cmd(ctx):
    """Find and download podcast episodes by show name or RSS URL."""
    # Pass through to the original fetch.main() with sys.argv adjustments
    import sys

    # Remove 'podx fetch' from sys.argv and call fetch.main()
    original_argv = sys.argv.copy()
    sys.argv = ["podx-fetch"] + sys.argv[2:]  # Keep original args after 'fetch'
    try:
        fetch.main()
    finally:
        sys.argv = original_argv


@main.command("transcode")
@click.pass_context
def transcode_cmd(ctx):
    """Convert audio files to different formats (wav16, mp3, aac)."""
    import sys

    original_argv = sys.argv.copy()
    sys.argv = ["podx-transcode"] + sys.argv[2:]
    try:
        transcode.main()
    finally:
        sys.argv = original_argv


@main.command("transcribe")
@click.pass_context
def transcribe_cmd(ctx):
    """Convert audio to text using Whisper ASR models."""
    import sys

    original_argv = sys.argv.copy()
    sys.argv = ["podx-transcribe"] + sys.argv[2:]
    try:
        transcribe.main()
    finally:
        sys.argv = original_argv


@main.command("align")
@click.pass_context
def align_cmd(ctx):
    """Add word-level timing alignment to transcripts using WhisperX."""
    import sys

    original_argv = sys.argv.copy()
    sys.argv = ["podx-align"] + sys.argv[2:]
    try:
        align.main()
    finally:
        sys.argv = original_argv


@main.command("diarize")
@click.pass_context
def diarize_cmd(ctx):
    """Add speaker identification to transcripts using WhisperX."""
    import sys

    original_argv = sys.argv.copy()
    sys.argv = ["podx-diarize"] + sys.argv[2:]
    try:
        diarize.main()
    finally:
        sys.argv = original_argv


@main.command("export")
@click.pass_context
def export_cmd(ctx):
    """Export transcripts to various formats (TXT, SRT, VTT, MD)."""
    import sys

    original_argv = sys.argv.copy()
    sys.argv = ["podx-export"] + sys.argv[2:]
    try:
        export.main()
    finally:
        sys.argv = original_argv


@main.command("deepcast")
@click.pass_context
def deepcast_cmd(ctx):
    """AI-powered transcript analysis and summarization."""
    import sys

    original_argv = sys.argv.copy()
    sys.argv = ["podx-deepcast"] + sys.argv[2:]
    try:
        deepcast.main()
    finally:
        sys.argv = original_argv


@main.command("notion")
@click.pass_context
def notion_cmd(ctx):
    """Upload processed content to Notion databases."""
    import sys

    original_argv = sys.argv.copy()
    sys.argv = ["podx-notion"] + sys.argv[2:]
    try:
        notion.main()
    finally:
        sys.argv = original_argv


# Add convenience workflow commands
@main.command("quick")
@click.option("--show", help="Podcast show name (iTunes search)")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
@click.option("--date", help="Episode date (YYYY-MM-DD)")
@click.option("--title-contains", help="Substring to match in episode title")
@click.option(
    "--model", default=lambda: get_config().default_asr_model, help="ASR model"
)
@click.option(
    "--compute",
    default=lambda: get_config().default_compute,
    type=click.Choice(["int8", "int8_float16", "float16", "float32"]),
    help="Compute type",
)
@click.option("-v", "--verbose", is_flag=True, help="Print interstitial outputs")
def quick(show, rss_url, date, title_contains, model, compute, verbose):
    """Quick workflow: fetch + transcribe only (fastest option)."""
    click.echo("🚀 Running quick transcription workflow...")

    # Use the existing run command but with minimal options
    ctx = click.get_current_context()
    ctx.invoke(
        run,
        show=show,
        rss_url=rss_url,
        date=date,
        title_contains=title_contains,
        model=model,
        compute=compute,
        verbose=verbose,
        # All other options default to False/None
        align=False,
        diarize=False,
        deepcast=False,
        notion=False,
        extract_markdown=False,
        clean=False,
    )


@main.command("analyze")
@click.option("--show", help="Podcast show name (iTunes search)")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
@click.option("--date", help="Episode date (YYYY-MM-DD)")
@click.option("--title-contains", help="Substring to match in episode title")
@click.option(
    "--model", default=lambda: get_config().default_asr_model, help="ASR model"
)
@click.option(
    "--compute",
    default=lambda: get_config().default_compute,
    type=click.Choice(["int8", "int8_float16", "float16", "float32"]),
    help="Compute type",
)
@click.option(
    "--deepcast-model",
    default=lambda: get_config().openai_model,
    help="AI analysis model",
)
@click.option(
    "--type",
    "podcast_type",
    type=click.Choice(
        [
            "interview",
            "tech",
            "business",
            "news",
            "educational",
            "narrative",
            "comedy",
            "general",
        ]
    ),
    help="Podcast type for specialized analysis",
)
@click.option("-v", "--verbose", is_flag=True, help="Print interstitial outputs")
def analyze(
    show,
    rss_url,
    date,
    title_contains,
    model,
    compute,
    deepcast_model,
    podcast_type,
    verbose,
):
    """Analysis workflow: transcribe + align + AI analysis (recommended)."""
    click.echo("🤖 Running analysis workflow...")

    ctx = click.get_current_context()
    ctx.invoke(
        run,
        show=show,
        rss_url=rss_url,
        date=date,
        title_contains=title_contains,
        model=model,
        compute=compute,
        deepcast_model=deepcast_model,
        verbose=verbose,
        # Analysis workflow options
        align=True,
        deepcast=True,
        extract_markdown=True,
        # Not included
        diarize=False,
        notion=False,
        clean=False,
    )


@main.command("publish")
@click.option("--show", help="Podcast show name (iTunes search)")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
@click.option("--date", help="Episode date (YYYY-MM-DD)")
@click.option("--title-contains", help="Substring to match in episode title")
@click.option(
    "--db",
    "notion_db",
    default=lambda: get_config().notion_db_id,
    help="Notion database ID",
)
@click.option(
    "--deepcast-model",
    default=lambda: get_config().openai_model,
    help="AI analysis model",
)
@click.option(
    "--type",
    "podcast_type",
    type=click.Choice(
        [
            "interview",
            "tech",
            "business",
            "news",
            "educational",
            "narrative",
            "comedy",
            "general",
        ]
    ),
    help="Podcast type for specialized analysis",
)
@click.option("-v", "--verbose", is_flag=True, help="Print interstitial outputs")
def publish(
    show,
    rss_url,
    date,
    title_contains,
    notion_db,
    deepcast_model,
    podcast_type,
    verbose,
):
    """Publishing workflow: full pipeline + Notion upload (complete)."""
    click.echo("📝 Running publishing workflow...")

    ctx = click.get_current_context()
    # This is equivalent to the --full flag
    ctx.invoke(
        run,
        show=show,
        rss_url=rss_url,
        date=date,
        title_contains=title_contains,
        notion_db=notion_db,
        deepcast_model=deepcast_model,
        verbose=verbose,
        # Full pipeline
        align=True,
        deepcast=True,
        extract_markdown=True,
        notion=True,
        clean=False,
    )


# Add utility commands
@main.command("help")
@click.argument("topic", required=False)
@click.option("--examples", is_flag=True, help="Show usage examples")
@click.option("--pipeline", is_flag=True, help="Show pipeline flow diagram")
def help_command(topic, examples, pipeline):
    """Enhanced help system with examples and pipeline diagrams."""
    ctx = click.get_current_context()
    ctx.invoke(help_cmd, examples=examples, pipeline=pipeline)


@main.command("list")
def list_commands():
    """List all available commands and workflows."""
    from rich.console import Console
    from rich.table import Table

    console = Console()

    table = Table(title="🎙️ Podx Commands")
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Description", style="white")

    # Core workflow commands
    table.add_row("browse", "Discovery", "Interactive episode browser")
    table.add_row("run", "Core", "Complete customizable pipeline")
    table.add_row("quick", "Workflow", "Fast transcription only")
    table.add_row("analyze", "Workflow", "Transcription + AI analysis")
    table.add_row("publish", "Workflow", "Full pipeline + Notion")

    table.add_section()

    # Individual commands
    table.add_row("browse", "Discovery", "Interactive episode selection")
    table.add_row("fetch", "Stage", "Download podcast episodes")
    table.add_row("transcode", "Stage", "Convert audio formats")
    table.add_row("transcribe", "Stage", "Speech-to-text conversion")
    table.add_row("align", "Stage", "Word-level timing alignment")
    table.add_row("diarize", "Stage", "Speaker identification")
    table.add_row("export", "Stage", "Export to various formats")
    table.add_row("deepcast", "Stage", "AI-powered analysis")
    table.add_row("notion", "Stage", "Upload to Notion")

    table.add_section()

    # Utility commands
    table.add_row("help", "Utility", "Enhanced help system")
    table.add_row("list", "Utility", "Show this command list")
    table.add_row("config", "Utility", "Configuration management")

    console.print(table)

    console.print("\n💡 [bold]Examples:[/bold]")
    console.print("  [cyan]podx quick --show 'The Podcast' --date 2024-01-15[/cyan]")
    console.print(
        "  [cyan]podx analyze --show 'Tech Talk' --date 2024-01-15 --type tech[/cyan]"
    )
    console.print(
        "  [cyan]podx publish --show 'Business Show' --date 2024-01-15[/cyan]"
    )
    console.print("  [cyan]podx help --examples[/cyan]")
    console.print("  [cyan]podx plugin list[/cyan]")

    # Show available plugins summary
    manager = PluginManager()
    manager.discover_plugins()
    plugins = manager.get_available_plugins()

    if plugins:
        console.print(
            f"\n🔌 [bold]Plugins Available:[/bold] {len(plugins)} plugins discovered"
        )
        type_counts = {}
        for metadata in plugins.values():
            type_name = metadata.plugin_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        plugin_summary = ", ".join(
            [f"{t}: {c}" for t, c in sorted(type_counts.items())]
        )
        console.print(f"  {plugin_summary}")
        console.print("  Use [cyan]podx plugin list[/cyan] for details")

        console.print("\n📝 [bold]Podcast Configurations:[/bold]")
        console.print(
            "  [cyan]podx podcast list[/cyan]        - List saved podcast configurations"
        )
        console.print(
            "  [cyan]podx podcast create[/cyan]      - Create podcast-specific settings"
        )
        console.print(
            "  [cyan]podx podcast init[/cyan]        - Setup popular podcast configs"
        )
        console.print("  [cyan]podx podcast show <name>[/cyan] - Show detailed config")
        console.print(
            "\n  💡 Podcast configs auto-apply settings like --align --deepcast --notion"
        )


@main.command("config")
@click.argument(
    "action",
    type=click.Choice(["show", "edit", "reset"]),
    required=False,
    default="show",
)
def config_command(action):
    """Configuration management for podx."""
    config = get_config()

    if action == "show":
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="🔧 Podx Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Environment Variable", style="yellow")

        # Show key configuration values
        table.add_row("ASR Model", config.default_asr_model, "PODX_DEFAULT_MODEL")
        table.add_row("Compute Type", config.default_compute, "PODX_DEFAULT_COMPUTE")
        table.add_row("OpenAI Model", config.openai_model, "OPENAI_MODEL")
        table.add_row(
            "OpenAI Temperature", str(config.openai_temperature), "OPENAI_TEMPERATURE"
        )
        table.add_row("Log Level", config.log_level, "PODX_LOG_LEVEL")
        table.add_row("Log Format", config.log_format, "PODX_LOG_FORMAT")
        table.add_row("Max Retries", str(config.max_retries), "PODX_MAX_RETRIES")

        # Show API keys status (without revealing them)
        openai_status = "✅ Set" if config.openai_api_key else "❌ Not set"
        notion_status = "✅ Set" if config.notion_token else "❌ Not set"

        table.add_row("OpenAI API Key", openai_status, "OPENAI_API_KEY")
        table.add_row("Notion Token", notion_status, "NOTION_TOKEN")
        table.add_row(
            "Notion DB ID", config.notion_db_id or "❌ Not set", "NOTION_DB_ID"
        )

        console.print(table)

        console.print(
            "\n💡 [bold]Tip:[/bold] Set environment variables in your shell or .env file"
        )

    elif action == "edit":
        click.echo("📝 Opening configuration help...")
        click.echo("\nTo configure podx, set these environment variables:")
        click.echo("  export PODX_DEFAULT_MODEL=medium.en")
        click.echo("  export OPENAI_API_KEY=your_key_here")
        click.echo("  export NOTION_TOKEN=your_token_here")
        click.echo("  export NOTION_DB_ID=your_db_id_here")
        click.echo("\nOr create a .env file in your project directory.")

    elif action == "reset":
        from .config import reset_config

        reset_config()
        click.echo(
            "✅ Configuration cache reset. New values will be loaded on next run."
        )


@main.group("plugin")
def plugin_group():
    """Plugin management commands."""
    pass


@plugin_group.command("list")
@click.option(
    "--type",
    "plugin_type",
    type=click.Choice([t.value for t in PluginType]),
    help="Filter by plugin type",
)
def list_plugins(plugin_type):
    """List available plugins."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = PluginManager()

    # Auto-discover plugins
    manager.discover_plugins()

    # Filter by type if specified
    filter_type = None
    if plugin_type:
        filter_type = PluginType(plugin_type)

    plugins = manager.get_available_plugins(filter_type)

    if not plugins:
        console.print("No plugins found.")
        return

    table = Table(title="🔌 Available Plugins")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Version", style="green")
    table.add_column("Description", style="white")
    table.add_column("Status", style="yellow")

    for name, metadata in plugins.items():
        status = "✅ Enabled" if metadata.enabled else "❌ Disabled"
        table.add_row(
            name,
            metadata.plugin_type.value,
            metadata.version,
            metadata.description,
            status,
        )

    console.print(table)

    # Show plugin type counts
    type_counts = {}
    for metadata in plugins.values():
        type_name = metadata.plugin_type.value
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    console.print(f"\n📊 Found {len(plugins)} plugins across {len(type_counts)} types")
    for plugin_type, count in sorted(type_counts.items()):
        console.print(f"  {plugin_type}: {count}")


@plugin_group.command("info")
@click.argument("plugin_name")
def plugin_info(plugin_name):
    """Show detailed information about a plugin."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    manager = PluginManager()
    manager.discover_plugins()

    registry = get_registry()
    plugin = registry.get_plugin(plugin_name)

    if not plugin:
        console.print(f"❌ Plugin '{plugin_name}' not found")
        return

    metadata = plugin.metadata

    # Create info panel
    info_text = f"""**Name:** {metadata.name}
**Version:** {metadata.version}  
**Author:** {metadata.author}
**Type:** {metadata.plugin_type.value}
**Status:** {"✅ Enabled" if metadata.enabled else "❌ Disabled"}

**Description:**
{metadata.description}"""

    if metadata.dependencies:
        info_text += f"\n\n**Dependencies:**\n{', '.join(metadata.dependencies)}"

    console.print(Panel(info_text, title=f"🔌 Plugin: {plugin_name}"))

    # Show configuration schema if available
    if metadata.config_schema:
        table = Table(title="⚙️ Configuration Schema")
        table.add_column("Parameter", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Required", style="red")
        table.add_column("Default", style="green")

        for param, schema in metadata.config_schema.items():
            param_type = schema.get("type", "string")
            required = "Yes" if schema.get("required", False) else "No"
            default = str(schema.get("default", "N/A"))

            table.add_row(param, param_type, required, default)

        console.print(table)


@plugin_group.command("discover")
@click.option(
    "--dir",
    "plugin_dirs",
    multiple=True,
    help="Additional directories to scan for plugins",
)
def discover_plugins(plugin_dirs):
    """Discover and load plugins from directories."""
    from rich.console import Console

    console = Console()
    manager = PluginManager()

    # Convert string paths to Path objects
    extra_dirs = [Path(d) for d in plugin_dirs] if plugin_dirs else []

    console.print("🔍 Discovering plugins...")

    # Discover plugins
    if extra_dirs:
        manager.discover_plugins(extra_dirs)
    else:
        manager.discover_plugins()

    plugins = manager.get_available_plugins()

    console.print(f"✅ Discovered {len(plugins)} plugins")

    # Show summary by type
    type_counts = {}
    for metadata in plugins.values():
        type_name = metadata.plugin_type.value
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    for plugin_type, count in sorted(type_counts.items()):
        console.print(f"  {plugin_type}: {count} plugins")


@plugin_group.command("create")
@click.argument("plugin_name")
@click.argument("plugin_type", type=click.Choice([t.value for t in PluginType]))
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=Path.cwd() / "plugins",
    help="Output directory for plugin template",
)
def create_plugin(plugin_name, plugin_type, output_dir):
    """Create a new plugin template."""
    from rich.console import Console

    from .plugins import create_plugin_template

    console = Console()

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create plugin template
    plugin_type_enum = PluginType(plugin_type)
    plugin_file = create_plugin_template(plugin_type_enum, plugin_name, output_dir)

    console.print(f"✅ Plugin template created: {plugin_file}")
    console.print(f"📝 Edit the file to implement your {plugin_type} plugin")
    console.print(f"📚 See documentation for {plugin_type} plugin interface details")


@plugin_group.command("test")
@click.argument("plugin_name")
def test_plugin(plugin_name):
    """Test a plugin's basic functionality."""
    from rich.console import Console

    console = Console()
    manager = PluginManager()
    manager.discover_plugins()

    registry = get_registry()
    plugin = registry.get_plugin(plugin_name)

    if not plugin:
        console.print(f"❌ Plugin '{plugin_name}' not found")
        return

    console.print(f"🧪 Testing plugin: {plugin_name}")

    # Test configuration validation
    try:
        config = {}  # Empty config for basic test
        valid = plugin.validate_config(config)
        status = "✅ Passed" if valid else "❌ Failed"
        console.print(f"  Config validation: {status}")
    except Exception as e:
        console.print(f"  Config validation: ❌ Error - {e}")

    # Test initialization (if config validation passed)
    try:
        plugin.initialize({})
        console.print("  Initialization: ✅ Passed")
    except Exception as e:
        console.print(f"  Initialization: ❌ Error - {e}")

    console.print(f"🏁 Plugin test completed for {plugin_name}")


@main.group("podcast")
def podcast_group():
    """Manage podcast-specific configurations for customized analysis."""
    pass


@podcast_group.command("list")
def podcast_list():
    """List all podcast-specific configurations."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = get_podcast_config_manager()
    configs = manager.list_configs()

    if not configs:
        console.print("📭 No podcast configurations found.")
        console.print(
            "\n💡 [bold]Tip:[/bold] Create configurations with [cyan]podx podcast create[/cyan]"
        )
        return

    table = Table(title="🎙️ Podcast Configurations")
    table.add_column("Show Name", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Default Flags", style="green")
    table.add_column("Description", style="blue")

    for config in configs.values():
        # Format default flags
        flags = []
        for flag, enabled in config.default_flags.items():
            if enabled:
                flags.append(flag)
        flags_str = ", ".join(flags) if flags else "None"

        table.add_row(
            config.show_name,
            config.podcast_type.value,
            flags_str,
            config.description or "No description",
        )

    console.print(table)


@podcast_group.command("show")
@click.argument("show_name")
def podcast_show(show_name: str):
    """Show detailed configuration for a specific podcast."""
    from rich.console import Console
    from rich.json import JSON
    from rich.panel import Panel

    console = Console()
    manager = get_podcast_config_manager()
    config = manager.get_config(show_name)

    if not config:
        console.print(f"❌ No configuration found for podcast: {show_name}")
        console.print(
            f'\n💡 [bold]Tip:[/bold] Create one with [cyan]podx podcast create "{show_name}"[/cyan]'
        )
        return

    # Show configuration details
    config_json = config.model_dump_json(indent=2)

    console.print(
        Panel(
            JSON(config_json),
            title=f"🎙️ Configuration for {config.show_name}",
            border_style="blue",
        )
    )


@podcast_group.command("create")
@click.argument("show_name")
@click.option(
    "--type",
    "podcast_type",
    type=click.Choice([t.value for t in PodcastType]),
    default="general",
    help="Podcast type for analysis",
)
@click.option("--align/--no-align", default=False, help="Default align flag")
@click.option("--diarize/--no-diarize", default=False, help="Default diarize flag")
@click.option("--deepcast/--no-deepcast", default=True, help="Default deepcast flag")
@click.option(
    "--extract-markdown/--no-extract-markdown",
    default=False,
    help="Default extract markdown flag",
)
@click.option("--notion/--no-notion", default=False, help="Default notion upload flag")
@click.option("--model", help="Preferred OpenAI model")
@click.option("--temperature", type=float, help="Analysis temperature")
@click.option("--description", help="Description of this configuration")
def podcast_create(
    show_name: str,
    podcast_type: str,
    align: bool,
    diarize: bool,
    deepcast: bool,
    extract_markdown: bool,
    notion: bool,
    model: Optional[str],
    temperature: Optional[float],
    description: Optional[str],
):
    """Create a new podcast-specific configuration."""
    from rich.console import Console

    console = Console()
    manager = get_podcast_config_manager()

    # Check if config already exists
    if manager.get_config(show_name):
        console.print(f"❌ Configuration for '{show_name}' already exists.")
        console.print(
            f'💡 Use [cyan]podx podcast update "{show_name}"[/cyan] to modify it.'
        )
        return

    # Create configuration
    config = PodcastAnalysisConfig(
        show_name=show_name,
        podcast_type=PodcastType(podcast_type),
        deepcast_model=model,
        temperature=temperature,
        default_flags={
            "align": align,
            "diarize": diarize,
            "deepcast": deepcast,
            "extract_markdown": extract_markdown,
            "notion": notion,
        },
        extract_markdown=extract_markdown,
        notion_upload=notion,
        description=description,
    )

    manager.save_config(config)
    console.print(f"✅ Created configuration for podcast: [cyan]{show_name}[/cyan]")
    console.print(f"🎯 Type: [yellow]{podcast_type}[/yellow]")


@podcast_group.command("delete")
@click.argument("show_name")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
def podcast_delete(show_name: str, yes: bool):
    """Delete a podcast configuration."""
    from rich.console import Console

    console = Console()
    manager = get_podcast_config_manager()

    if not manager.get_config(show_name):
        console.print(f"❌ No configuration found for podcast: {show_name}")
        return

    if not yes:
        if not click.confirm(f"Delete configuration for '{show_name}'?"):
            console.print("Cancelled.")
            return

    if manager.delete_config(show_name):
        console.print(f"✅ Deleted configuration for: [cyan]{show_name}[/cyan]")
    else:
        console.print(f"❌ Failed to delete configuration for: {show_name}")


@podcast_group.command("init")
def podcast_init():
    """Initialize predefined podcast configurations."""
    from rich.console import Console

    console = Console()
    console.print("🚀 Creating predefined podcast configurations...")

    create_predefined_configs()

    console.print("✅ Predefined configurations created:")
    for show_name in PREDEFINED_CONFIGS.keys():
        console.print(f"  • [cyan]{show_name}[/cyan]")

    console.print(f"\n💡 View all configs with [cyan]podx podcast list[/cyan]")


@main.group("config")
def config_group():
    """Advanced YAML-based configuration management."""
    pass


@config_group.command("init")
def config_init():
    """Create an example YAML configuration file."""
    from rich.console import Console

    console = Console()
    manager = get_yaml_config_manager()

    # Check if config already exists
    if manager.config_file.exists():
        console.print(f"⚠️  Configuration file already exists at: {manager.config_file}")
        if not click.confirm("Overwrite existing configuration?"):
            console.print("Cancelled.")
            return

    # Create example config
    manager.create_example_config()
    console.print(
        f"✅ Created example YAML configuration at: [cyan]{manager.config_file}[/cyan]"
    )
    console.print(f"\n📝 Edit this file to customize your podcast processing settings:")
    console.print(f"   - Multiple Notion databases with different API keys")
    console.print(f"   - Podcast-specific analysis types and prompts")
    console.print(f"   - Global pipeline defaults")
    console.print(f"   - Custom variables and advanced settings")


@config_group.command("show")
def config_show():
    """Show current YAML configuration."""
    from rich.console import Console
    from rich.syntax import Syntax

    console = Console()
    manager = get_yaml_config_manager()

    if not manager.config_file.exists():
        console.print("❌ No YAML configuration found.")
        console.print(f"💡 Create one with [cyan]podx config init[/cyan]")
        return

    # Read and display config file
    config_content = manager.config_file.read_text()
    syntax = Syntax(config_content, "yaml", theme="monokai", line_numbers=True)

    console.print(f"📝 Configuration: [cyan]{manager.config_file}[/cyan]")
    console.print(syntax)


@config_group.command("validate")
def config_validate():
    """Validate YAML configuration syntax and settings."""
    from rich.console import Console

    console = Console()
    manager = get_yaml_config_manager()

    if not manager.config_file.exists():
        console.print("❌ No YAML configuration found.")
        return

    try:
        config = manager.load_config()
        console.print("✅ Configuration is valid!")

        # Show summary
        if config.podcasts:
            console.print(f"📋 Found {len(config.podcasts)} podcast mappings")
        if config.notion_databases:
            console.print(f"🗃️  Found {len(config.notion_databases)} Notion databases")
        if config.defaults:
            console.print(f"⚙️  Global defaults configured")

    except Exception as e:
        console.print(f"❌ Configuration validation failed: {e}")
        console.print(f"💡 Check your YAML syntax and fix any errors")


@config_group.command("databases")
def config_databases():
    """List configured Notion databases."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    manager = get_yaml_config_manager()
    databases = manager.list_notion_databases()

    if not databases:
        console.print("📭 No Notion databases configured.")
        console.print(
            f"💡 Add them to your YAML config: [cyan]{manager.config_file}[/cyan]"
        )
        return

    table = Table(title="🗃️ Configured Notion Databases")
    table.add_column("Name", style="cyan")
    table.add_column("Database ID", style="yellow")
    table.add_column("Title Property", style="green")
    table.add_column("Description", style="blue")

    for name, db in databases.items():
        # Mask the database ID for security
        masked_id = (
            db.database_id[:8] + "..." + db.database_id[-8:]
            if len(db.database_id) > 16
            else db.database_id
        )

        table.add_row(
            name, masked_id, db.title_property, db.description or "No description"
        )

    console.print(table)


if __name__ == "__main__":
    main()
