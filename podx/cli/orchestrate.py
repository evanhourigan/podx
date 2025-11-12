#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

# Use rich-click for colorized --help when available
try:  # pragma: no cover
    import click  # type: ignore
    import rich_click  # type: ignore

    # Style configuration (approximate the standard color convention)
    rc = rich_click.rich_click
    rc.STYLE_HEADING = "bold bright_green"
    rc.STYLE_USAGE = "bold white"
    rc.STYLE_COMMAND = "bold white"
    rc.STYLE_METAVAR = "yellow"
    rc.STYLE_SWITCH = "bright_black"  # flags
    rc.STYLE_OPTION = "bright_black"  # flags
    rc.STYLE_ARGUMENT = "yellow"  # flag arguments
    rc.STYLE_HELP = "white"
    rc.GROUP_ARGUMENTS_OPTIONS = True
    rc.MAX_WIDTH = 100

    BaseGroup = rich_click.RichGroup
except Exception:  # pragma: no cover
    import click  # type: ignore

    BaseGroup = click.Group

from podx.cli.help import help_cmd

# Import services for command execution and orchestration
from .services import (
    build_episode_metadata_display,
    build_pipeline_config,
    display_pipeline_config,
    execute_cleanup,
    execute_deepcast,
    execute_enhancement,
    execute_export_final,
    execute_export_formats,
    execute_fetch,
    execute_notion_upload,
    execute_transcribe,
    handle_interactive_mode,
    print_results_summary,
    run_command,
    run_passthrough,
)

# Import individual command modules for CLI integration
from podx.config import get_config
from podx.constants import (
    DEFAULT_ENCODING,
    JSON_INDENT,
    MIN_NOTION_DB_ID_LENGTH,
)
from podx.logging import get_logger, setup_logging
from podx.progress import PodxProgress, print_podx_header
from podx.yaml_config import get_yaml_config_manager

# Initialize logging
setup_logging()
logger = get_logger(__name__)

# Alias for backwards compatibility within this module
_run = run_command
_run_passthrough = run_passthrough
_build_pipeline_config = build_pipeline_config
_execute_fetch = execute_fetch
_execute_transcribe = execute_transcribe
_execute_enhancement = execute_enhancement
_execute_deepcast = execute_deepcast
_execute_notion_upload = execute_notion_upload
_execute_cleanup = execute_cleanup
_execute_export_formats = execute_export_formats
_execute_export_final = execute_export_final
_print_results_summary = print_results_summary
_display_pipeline_config = display_pipeline_config
_build_episode_metadata_display = build_episode_metadata_display
_handle_interactive_mode = handle_interactive_mode


class PodxGroup(BaseGroup):
    """Custom group to hide deprecated commands from help."""

    def list_commands(self, ctx):  # type: ignore[override]
        commands = super().list_commands(ctx)
        # Filter hidden and deprecated workflow aliases from help
        hidden_names = {"quick", "analyze", "publish"}
        return [name for name in commands if name not in hidden_names]


@click.group(cls=PodxGroup)
def main():
    """Podx — composable podcast pipeline

    Core idea: small tools that do one thing well and compose cleanly.

    Core commands (composable):
      fetch, transcode, transcribe, preprocess, diarize, export, deepcast, notion

    Orchestrator:
      run  — drive the pipeline end‑to‑end with flags (or interactive mode)

    Tips:
    - Use 'podx COMMAND --help' for details on each tool
    - Use 'podx help --examples' for copy‑paste examples
    - All tools read JSON from stdin and write JSON to stdout so you can pipe them
    """
    pass


@main.command("run", help="Orchestrate the complete podcast processing pipeline.")
@click.option("--show", help="Podcast show name (iTunes search)")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
@click.option(
    "--youtube-url", help="YouTube video URL (alternative to --show and --rss-url)"
)
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
    "--asr-provider",
    type=click.Choice(["auto", "local", "openai", "hf"]),
    default="auto",
    help="ASR provider (auto-detect by model prefix/alias if 'auto')",
)
@click.option(
    "--compute",
    default=lambda: get_config().default_compute,
    type=click.Choice(["auto", "int8", "int8_float16", "float16", "float32"]),
    help="Compute type",
)
@click.option(
    "--preprocess/--no-preprocess",
    default=True,
    help="Run preprocessing (merge/normalize) before diarization/deepcast (default: enabled)",
)
@click.option(
    "--restore/--no-restore",
    default=False,
    help="When preprocessing, attempt semantic restore using an LLM",
)
@click.option(
    "--diarize/--no-diarize",
    default=True,
    help="Run diarization (default: enabled; use --no-diarize to skip)",
)
@click.option(
    "--deepcast/--no-deepcast",
    default=True,
    help="Run LLM summarization (default: enabled; use --no-deepcast to skip)",
)
@click.option(
    "--interactive",
    "interactive_select",
    is_flag=True,
    help="Browse existing episodes and select one to process",
)
@click.option(
    "--scan-dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Directory to scan for episodes when using --interactive",
)
@click.option(
    "--fetch-new",
    is_flag=True,
    help="When used with --interactive and --show, open fetch browser to add new episodes before selection",
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
    "--extract-markdown/--no-markdown",
    "extract_markdown",
    default=True,
    help="Extract markdown file when running deepcast (default: enabled)",
)
@click.option(
    "--deepcast-pdf",
    "deepcast_pdf",
    is_flag=True,
    help="Also render a PDF of the deepcast markdown (requires pandoc)",
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
    "--model-prop",
    default="Model",
    help="Notion property name for deepcast model",
)
@click.option(
    "--asr-prop",
    default="ASR Model",
    help="Notion property name for ASR model",
)
@click.option(
    "--append-content",
    is_flag=True,
    help="Append to page body in Notion instead of replacing (default: replace)",
)
@click.option(
    "--full",
    is_flag=True,
    help="Enable full pipeline: --deepcast --extract-markdown --notion (convenience flag)",
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
    youtube_url: Optional[str],
    date: Optional[str],
    title_contains: Optional[str],
    workdir: Optional[Path],
    fmt: str,
    model: str,
    compute: str,
    asr_provider: str,
    preprocess: bool,
    restore: bool,
    diarize: bool,
    deepcast: bool,
    interactive_select: bool,
    scan_dir: Path,
    fetch_new: bool,
    deepcast_model: str,
    deepcast_temp: float,
    extract_markdown: bool,
    deepcast_pdf: bool,
    notion: bool,
    notion_db: Optional[str],
    podcast_prop: str,
    date_prop: str,
    episode_prop: str,
    model_prop: str,
    asr_prop: str,
    append_content: bool,
    full: bool,
    verbose: bool,
    clean: bool,
    no_keep_audio: bool,
):
    """Orchestrate the complete podcast processing pipeline.

    This function handles the end-to-end workflow from episode fetch to publication,
    supporting various pipeline configurations and resume capabilities.

    Pipeline Flow (v2.0 - simplified):
        1. Source Selection: Fetch from RSS, YouTube, or interactive browser
        2. Audio Processing: Transcode to target format
        3. Transcription: ASR transcription
        4. Enhancement: Diarization (with internal alignment), preprocessing
        5. Analysis: AI-powered deepcast with configurable types (default: ON)
        6. Export: Markdown extraction (default: ON)
        7. Publication: Optional Notion upload

    v2.0 Defaults (enabled by default):
        - Diarization, Preprocessing, Deepcast, Markdown extraction
        - Use --no-diarize, --no-preprocess, --no-deepcast, --no-markdown to disable

    Resume Support:
        The function detects existing artifacts and offers to skip completed steps,
        maintaining state in run-state.json for crash recovery.

    Args:
        show: Podcast name for iTunes search (alternative to rss_url/youtube_url)
        rss_url: Direct RSS feed URL
        youtube_url: YouTube video/channel URL
        date: Filter episode by date (YYYY-MM-DD or partial)
        title_contains: Filter episode by title substring
        workdir: Working directory path (auto-generated if not specified)
        fmt: Output audio format (wav16/mp3/aac)
        model: ASR transcription model
        compute: ASR compute type (int8/float16/float32)
        asr_provider: ASR provider (auto/local/openai/hf)
        preset: ASR preset (balanced/precision/recall)
        align: Enable word-level alignment (WhisperX)
        preprocess: Enable transcript preprocessing
        restore: Enable semantic restore (LLM-based)
        diarize: Enable speaker diarization (WhisperX)
        deepcast: Enable AI analysis
        interactive_select: Use interactive episode selection UI
        scan_dir: Directory to scan for episodes in interactive mode
        fetch_new: Force fetch new episode (skip interactive selection)
        deepcast_model: AI model for deepcast analysis
        deepcast_temp: Temperature for deepcast LLM calls
        extract_markdown: Extract markdown from deepcast output
        deepcast_pdf: Generate PDF from deepcast output
        notion: Upload to Notion
        notion_db: Notion database key (from YAML config)
        podcast_prop: Notion property name for podcast
        date_prop: Notion property name for date
        episode_prop: Notion property name for episode
        model_prop: Notion property name for model
        asr_prop: Notion property name for ASR provider
        append_content: Append to existing Notion page instead of replacing
        full: Convenience flag to enable align + deepcast + markdown + notion
        verbose: Enable verbose logging
        clean: Clean intermediate files after completion
        no_keep_audio: Don't keep audio files after transcription

    Raises:
        ValidationError: On configuration or input validation failures
        SystemExit: On user cancellation or missing required configuration

    Returns:
        Exits with status code 0 on success, non-zero on failure
    """
    # 1. Build pipeline configuration from CLI args with preset transformations
    config = _build_pipeline_config(
        show=show,
        rss_url=rss_url,
        youtube_url=youtube_url,
        date=date,
        title_contains=title_contains,
        workdir=workdir,
        fmt=fmt,
        model=model,
        compute=compute,
        asr_provider=asr_provider,
        preprocess=preprocess,
        restore=restore,
        diarize=diarize,
        deepcast=deepcast,
        deepcast_model=deepcast_model,
        deepcast_temp=deepcast_temp,
        extract_markdown=extract_markdown,
        deepcast_pdf=deepcast_pdf,
        notion=notion,
        notion_db=notion_db,
        podcast_prop=podcast_prop,
        date_prop=date_prop,
        episode_prop=episode_prop,
        model_prop=model_prop,
        asr_prop=asr_prop,
        append_content=append_content,
        full=full,
        verbose=verbose,
        clean=clean,
        no_keep_audio=no_keep_audio,
    )

    # Print header and start progress tracking
    print_podx_header()

    start_time = time.time()

    # Initialize results dictionary
    results = {}

    # Use progress tracking for the entire pipeline
    with PodxProgress() as progress:
        # We'll determine the actual workdir after fetching metadata
        wd = None  # Will be set after fetch

        # 2. Interactive selection: choose existing episode and configure pipeline
        interactive_meta = None
        interactive_wd = None
        if interactive_select:
            from podx.ui import make_console

            console = make_console()
            interactive_meta, interactive_wd = _handle_interactive_mode(
                config, scan_dir, console
            )

            # Suppress logging during pipeline execution in interactive mode
            from podx.logging import suppress_logging

            suppress_logging()

        # 3. Fetch episode metadata and determine working directory
        meta, wd = _execute_fetch(
            config=config,
            interactive_mode_meta=interactive_meta,
            interactive_mode_wd=interactive_wd,
            progress=progress,
            verbose=config["verbose"],
        )

        # Show pipeline configuration (after YAML/JSON config is applied)
        steps = _display_pipeline_config(
            align=config["align"],
            diarize=config["diarize"],
            deepcast=config["deepcast"],
            notion=config["notion"],
            show=config["show"],
            rss_url=config["rss_url"],
            date=config["date"],
            model=config["model"],
            compute=config["compute"],
        )

        # Working directory determined by _execute_fetch()
        wd.mkdir(parents=True, exist_ok=True)

        # For YouTube URLs, now do the full fetch with proper workdir
        if config["youtube_url"]:
            from .youtube import fetch_youtube_episode

            progress.start_step("Downloading YouTube audio")
            meta = fetch_youtube_episode(config["youtube_url"], wd)
            progress.complete_step(f"YouTube audio downloaded: {wd / '*.mp3'}")
        # Save metadata to the determined workdir
        (wd / "episode-meta.json").write_text(json.dumps(meta, indent=2))

        # Track original audio path for cleanup
        original_audio_path = Path(meta["audio_path"]) if "audio_path" in meta else None

        # 2) TRANSCODE → audio-meta.json
        audio_meta_file = wd / "audio-meta.json"
        if audio_meta_file.exists():
            logger.info("Found existing audio metadata, skipping transcode")
            audio = json.loads(audio_meta_file.read_text())
            progress.complete_step(f"Using existing {config['fmt']} audio", 0)
        else:
            progress.start_step(f"Transcoding audio to {config['fmt']}")
            step_start = time.time()
            from .services import CommandBuilder

            # Convert fmt enum to string value if needed
            fmt_value = (
                config["fmt"].value
                if hasattr(config["fmt"], "value")
                else config["fmt"]
            )

            transcode_cmd = (
                CommandBuilder("podx-transcode")
                .add_option("--to", fmt_value)
                .add_option("--outdir", str(wd))
            )
            audio = _run(
                transcode_cmd.build(),
                stdin_payload=meta,
                verbose=config["verbose"],
                save_to=audio_meta_file,
                label=None,  # Progress handles the display
            )
            step_duration = time.time() - step_start
            progress.complete_step(
                f"Audio transcoded to {config['fmt']}", step_duration
            )

        # Track transcoded audio path for cleanup
        transcoded_path = Path(audio["audio_path"])

        # 3) TRANSCRIBE → transcript-{model}.json
        latest, latest_name = _execute_transcribe(
            model=config["model"],
            compute=config["compute"],
            asr_provider=config["asr_provider"],
            audio=audio,
            wd=wd,
            progress=progress,
            verbose=config["verbose"],
        )

        # 4-6) ENHANCEMENT PIPELINE (preprocess, align, diarize)
        latest, latest_name = _execute_enhancement(
            preprocess=config["preprocess"],
            restore=config["restore"],
            align=config["align"],
            diarize=config["diarize"],
            model=config["model"],
            latest=latest,
            latest_name=latest_name,
            wd=wd,
            progress=progress,
            verbose=config["verbose"],
        )

        # Always keep a pointer to the latest JSON/SRT/TXT for convenience
        (wd / "latest.json").write_text(
            json.dumps(latest, indent=JSON_INDENT), encoding=DEFAULT_ENCODING
        )

        # Export to TXT/SRT formats and build results dictionary
        results = _execute_export_formats(
            latest=latest,
            latest_name=latest_name,
            wd=wd,
            progress=progress,
            verbose=config["verbose"],
        )

        # 7) DEEPCAST (optional)
        _execute_deepcast(
            deepcast=config["deepcast"],
            model=config["model"],
            deepcast_model=config["deepcast_model"],
            deepcast_temp=config["deepcast_temp"],
            yaml_analysis_type=config["yaml_analysis_type"],
            extract_markdown=config["extract_markdown"],
            deepcast_pdf=config["deepcast_pdf"],
            wd=wd,
            results=results,
            progress=progress,
            verbose=config["verbose"],
        )

        # Final export step (write exported-<timestamp>.* from deepcast)
        _execute_export_final(
            preset=config["preset"],
            deepcast_pdf=config["deepcast_pdf"],
            wd=wd,
            results=results,
        )

        # 7) NOTION (optional) — requires DB id
        if config["notion"]:
            if not config["notion_db"]:
                raise SystemExit(
                    "Please pass --db or set NOTION_DB_ID environment variable"
                )

            _execute_notion_upload(
                notion_db=config["notion_db"],
                wd=wd,
                results=results,
                deepcast_model=config["deepcast_model"],
                model=config["model"],
                podcast_prop=config["podcast_prop"],
                date_prop=config["date_prop"],
                episode_prop=config["episode_prop"],
                model_prop=config["model_prop"],
                asr_prop=config["asr_prop"],
                append_content=config["append_content"],
                progress=progress,
                verbose=config["verbose"],
            )

        # 8) Optional cleanup
        _execute_cleanup(
            clean=config["clean"],
            no_keep_audio=config["no_keep_audio"],
            wd=wd,
            latest_name=latest_name,
            transcoded_path=transcoded_path,
            original_audio_path=original_audio_path,
            progress=progress,
        )

    # Final summary
    _print_results_summary(
        start_time=start_time,
        steps=steps,
        wd=wd,
        results=results,
    )


# Add individual commands as subcommands to main CLI group
# This provides a consistent interface: podx <command> instead of podx-<command>


## Deprecated: info command has been removed in favor of 'podx list'


@main.command(
    "fetch",
    help="Shim: run podx-fetch with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],  # Disable Click's --help handling
    },
)
@click.pass_context
def fetch_cmd(ctx):
    """Find and download podcast episodes by show name or RSS URL."""
    code = _run_passthrough(["podx-fetch"] + ctx.args)
    sys.exit(code)


@main.command(
    "transcode",
    help="Shim: run podx-transcode with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def transcode_cmd(ctx):
    """Convert audio files to different formats (wav16, mp3, aac)."""
    code = _run_passthrough(["podx-transcode"] + ctx.args)
    sys.exit(code)


@main.command(
    "transcribe",
    help="Shim: run podx-transcribe with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def transcribe_cmd(ctx):
    """Convert audio to text using Whisper ASR models."""
    code = _run_passthrough(["podx-transcribe"] + ctx.args)
    sys.exit(code)


@main.command(
    "diarize",
    help="Shim: run podx-diarize with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def diarize_cmd(ctx):
    """Add speaker identification to transcripts using WhisperX."""
    code = _run_passthrough(["podx-diarize"] + ctx.args)
    sys.exit(code)


@main.command(
    "export",
    help="Shim: run podx-export with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def export_cmd(ctx):
    """Export transcripts to various formats (TXT, SRT, VTT, MD)."""
    code = _run_passthrough(["podx-export"] + ctx.args)
    sys.exit(code)


@main.command(
    "deepcast",
    help="Shim: run podx-deepcast with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def deepcast_cmd(ctx):
    """AI-powered transcript analysis and summarization."""
    code = _run_passthrough(["podx-deepcast"] + ctx.args)
    sys.exit(code)


@main.command(
    "models",
    help="Shim: run podx-models with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def models_cmd(ctx):
    """List AI models with pricing and estimate deepcast cost."""
    code = _run_passthrough(["podx-models"] + ctx.args)
    sys.exit(code)


@main.command(
    "notion",
    help="Shim: run podx-notion with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def notion_cmd(ctx):
    """Upload processed content to Notion databases."""
    code = _run_passthrough(["podx-notion"] + ctx.args)
    sys.exit(code)


# Add convenience workflow commands
@main.command("quick", hidden=True)
@click.option("--show", help="Podcast show name (iTunes search)")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
@click.option(
    "--youtube-url", help="YouTube video URL (alternative to --show and --rss-url)"
)
@click.option("--date", help="Episode date (YYYY-MM-DD)")
@click.option("--title-contains", help="Substring to match in episode title")
@click.option(
    "--model", default=lambda: get_config().default_asr_model, help="ASR model"
)
@click.option(
    "--asr-provider",
    type=click.Choice(["auto", "local", "openai", "hf"]),
    default="auto",
    help="ASR provider for transcribe",
)
@click.option(
    "--compute",
    default=lambda: get_config().default_compute,
    type=click.Choice(["auto", "int8", "int8_float16", "float16", "float32"]),
    help="Compute type",
)
@click.option("-v", "--verbose", is_flag=True, help="Print interstitial outputs")
def quick(
    show,
    rss_url,
    youtube_url,
    date,
    title_contains,
    model,
    asr_provider,
    compute,
    verbose,
):
    """Quick workflow: fetch + transcribe only (fastest option)."""
    click.secho("[deprecated] Use: podx run (with no extra flags)", fg="yellow")
    click.echo("🚀 Running quick transcription workflow...")

    # Use the existing run command but with minimal options (all flags defaulted to False)
    ctx = click.get_current_context()
    ctx.invoke(
        run,
        show=show,
        rss_url=rss_url,
        youtube_url=youtube_url,
        date=date,
        title_contains=title_contains,
        model=model,
        compute=compute,
        asr_provider=asr_provider,
        align=False,
        diarize=False,
        deepcast=False,
        extract_markdown=False,
        notion=False,
        verbose=verbose,
        clean=False,
        model_prop="Model",
    )


@main.command("analyze", hidden=True)
@click.option("--show", help="Podcast show name (iTunes search)")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
@click.option(
    "--youtube-url", help="YouTube video URL (alternative to --show and --rss-url)"
)
@click.option("--date", help="Episode date (YYYY-MM-DD)")
@click.option("--title-contains", help="Substring to match in episode title")
@click.option(
    "--model", default=lambda: get_config().default_asr_model, help="ASR model"
)
@click.option(
    "--asr-provider",
    type=click.Choice(["auto", "local", "openai", "hf"]),
    default="auto",
    help="ASR provider for transcribe",
)
@click.option(
    "--compute",
    default=lambda: get_config().default_compute,
    type=click.Choice(["auto", "int8", "int8_float16", "float16", "float32"]),
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
    youtube_url,
    date,
    title_contains,
    model,
    asr_provider,
    compute,
    deepcast_model,
    podcast_type,
    verbose,
):
    """Analysis workflow: transcribe + AI analysis (recommended)."""
    click.secho(
        "[deprecated] Use: podx run (deepcast + markdown enabled by default in v2.0)",
        fg="yellow",
    )
    click.echo("🤖 Running analysis workflow...")

    ctx = click.get_current_context()
    ctx.invoke(
        run,
        show=show,
        rss_url=rss_url,
        youtube_url=youtube_url,
        date=date,
        title_contains=title_contains,
        model=model,
        compute=compute,
        asr_provider=asr_provider,
        align=True,
        deepcast=True,
        extract_markdown=True,
        deepcast_model=deepcast_model,
        verbose=verbose,
        clean=False,
        model_prop="Model",
    )


@main.command("publish", hidden=True)
@click.option("--show", help="Podcast show name (iTunes search)")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
@click.option(
    "--youtube-url", help="YouTube video URL (alternative to --show and --rss-url)"
)
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
    youtube_url,
    date,
    title_contains,
    notion_db,
    deepcast_model,
    podcast_type,
    verbose,
):
    """Publishing workflow: full pipeline + Notion upload (complete)."""
    click.secho(
        "[deprecated] Use: podx run --notion (deepcast + markdown enabled by default in v2.0)",
        fg="yellow",
    )
    click.echo("📝 Running publishing workflow...")

    ctx = click.get_current_context()
    # Equivalent to selecting the publish workflow
    ctx.invoke(
        run,
        show=show,
        rss_url=rss_url,
        youtube_url=youtube_url,
        date=date,
        title_contains=title_contains,
        notion_db=notion_db,
        deepcast_model=deepcast_model,
        align=True,
        deepcast=True,
        extract_markdown=True,
        notion=True,
        verbose=verbose,
        clean=False,
        model_prop="Model",
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


# Removed: podx list command - podx-list does not exist


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
        from podx.config import reset_config

        reset_config()
        click.echo(
            "✅ Configuration cache reset. New values will be loaded on next run."
        )


# Lightweight shims to expose individual tools under the unified `podx` namespace
@main.command("preprocess", help="Shim: run podx-preprocess with the given arguments")
@click.argument("args", nargs=-1)
def preprocess_shim(args: tuple[str, ...]):
    code = _run_passthrough(["podx-preprocess", *args])
    sys.exit(code)


# Removed: podx agreement and podx consensus commands - these tools were removed from the codebase


# Removed: podx plugin command group - plugin system was unused and has been removed


# Deprecated: 'podx podcast' removed in favor of YAML presets (podx config ...)


## (all 'podx podcast' subcommands removed)


## (removed)


## (removed)


## (removed)


## (removed)


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
    console.print("\n📝 Edit this file to customize your podcast processing settings:")
    console.print("   - Multiple Notion databases with different API keys")
    console.print("   - Podcast-specific analysis types and prompts")
    console.print("   - Global pipeline defaults")
    console.print("   - Custom variables and advanced settings")


@config_group.command("show")
def config_show():
    """Show current YAML configuration."""
    from rich.console import Console
    from rich.syntax import Syntax

    console = Console()
    manager = get_yaml_config_manager()

    if not manager.config_file.exists():
        console.print("❌ No YAML configuration found.")
        console.print("💡 Create one with [cyan]podx config init[/cyan]")
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
            console.print("⚙️  Global defaults configured")

    except Exception as e:
        console.print(f"❌ Configuration validation failed: {e}")
        console.print("💡 Check your YAML syntax and fix any errors")


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
    table.add_column("Token", style="magenta")
    table.add_column("Podcast Prop", style="green")
    table.add_column("Date Prop", style="green")
    table.add_column("Episode Prop", style="green")
    table.add_column("Description", style="blue")

    for name, db in databases.items():
        # Mask the database ID for security
        masked_id = (
            db.database_id[:8] + "..." + db.database_id[-8:]
            if len(db.database_id) > MIN_NOTION_DB_ID_LENGTH
            else db.database_id
        )

        def _mask(value: Optional[str]) -> str:
            if not value:
                return "(none)"
            if len(value) <= 10:
                return value
            return f"{value[:6]}…{value[-4:]}"

        masked_id = _mask(db.database_id)
        masked_token = _mask(db.token)

        table.add_row(
            name,
            masked_id,
            masked_token,
            db.podcast_property,
            db.date_property,
            db.episode_property,
            db.description or "No description",
        )

    console.print(table)


# ============================================================================
# Removed: Plugin Management Commands (plugin system was unused and removed)
# ============================================================================


# ============================================================================
# Standalone Entry Points
# ============================================================================


def run_main():
    """Entry point for podx-run standalone command."""
    # Invoke the main CLI with 'run' subcommand and pass all args
    sys.argv = ["podx", "run"] + sys.argv[1:]
    main()


if __name__ == "__main__":
    main()
