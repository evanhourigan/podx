"""Main run command for orchestrating the complete podcast processing pipeline."""

import json
import time
from pathlib import Path
from typing import Optional

import click

from podx.cli.services.command_runner import run_command
from podx.cli.services.config_builder import build_pipeline_config
from podx.cli.services.pipeline_steps import (
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
)
from podx.config import get_config
from podx.constants import DEFAULT_ENCODING, JSON_INDENT
from podx.logging import get_logger
from podx.progress import PodxProgress, print_podx_header

logger = get_logger(__name__)


@click.command("run", help="Orchestrate the complete podcast processing pipeline.")
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
    "--keep-intermediates/--no-keep-intermediates",
    default=False,
    help="Keep intermediate files after pipeline completion (default: auto-cleanup)",
)
@click.option(
    "--keep-audio/--no-keep-audio",
    default=True,
    help="Keep audio files when cleaning up intermediates (default: keep audio)",
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
    keep_intermediates: bool,
    keep_audio: bool,
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
        keep_intermediates: Keep intermediate files after completion (default: cleanup)
        keep_audio: Keep audio files when cleaning intermediates (default: keep)

    Raises:
        ValidationError: On configuration or input validation failures
        SystemExit: On user cancellation or missing required configuration

    Returns:
        Exits with status code 0 on success, non-zero on failure
    """
    # 1. Build pipeline configuration from CLI args with preset transformations
    config = build_pipeline_config(
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
        clean=not keep_intermediates,  # Invert: cleanup by default unless keeping
        no_keep_audio=not keep_audio,  # Invert: keep audio by default unless not keeping
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
            interactive_meta, interactive_wd = handle_interactive_mode(
                config, scan_dir, console
            )

            # Suppress logging during pipeline execution in interactive mode
            from podx.logging import suppress_logging

            suppress_logging()

        # 3. Fetch episode metadata and determine working directory
        meta, wd = execute_fetch(
            config=config,
            interactive_mode_meta=interactive_meta,
            interactive_mode_wd=interactive_wd,
            progress=progress,
            verbose=config["verbose"],
        )

        # Show pipeline configuration (after YAML/JSON config is applied)
        steps = display_pipeline_config(
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

        # Working directory determined by execute_fetch()
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
            from podx.cli.services import CommandBuilder

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
            audio = run_command(
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
        latest, latest_name = execute_transcribe(
            model=config["model"],
            compute=config["compute"],
            asr_provider=config["asr_provider"],
            audio=audio,
            wd=wd,
            progress=progress,
            verbose=config["verbose"],
        )

        # 4-6) ENHANCEMENT PIPELINE (preprocess, align, diarize)
        latest, latest_name = execute_enhancement(
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
        results = execute_export_formats(
            latest=latest,
            latest_name=latest_name,
            wd=wd,
            progress=progress,
            verbose=config["verbose"],
        )

        # 7) DEEPCAST (optional)
        execute_deepcast(
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
        execute_export_final(
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

            execute_notion_upload(
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
        execute_cleanup(
            clean=config["clean"],
            no_keep_audio=config["no_keep_audio"],
            wd=wd,
            latest_name=latest_name,
            transcoded_path=transcoded_path,
            original_audio_path=original_audio_path,
            progress=progress,
        )

    # Final summary
    print_results_summary(
        start_time=start_time,
        steps=steps,
        wd=wd,
        results=results,
    )


# Add individual commands as subcommands to main CLI group
# This provides a consistent interface: podx <command> instead of podx-<command>


## Deprecated: info command has been removed in favor of 'podx list'
