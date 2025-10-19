#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
import sys
from typing import Dict, List, Optional

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

# Import individual command modules for CLI integration
from . import (
    align,
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
from .help import help_cmd
from .logging import get_logger, setup_logging
from .plugins import PluginManager, PluginType, get_registry
from .progress import (
    PodxProgress,
    format_duration,
    print_podx_header,
    print_podx_info,
    print_podx_success,
)
from .export import export_from_deepcast_json
from .yaml_config import get_yaml_config_manager

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


def _run_passthrough(cmd: List[str]) -> int:
    """Run a CLI tool in passthrough mode (inherit stdio). Returns returncode.

    Use this for interactive child processes so the user sees the UI and can interact.
    """
    proc = subprocess.run(cmd)
    return proc.returncode


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
      fetch, transcode, transcribe, preprocess, align, diarize, export, deepcast, agreement, consensus, notion

    Orchestrator:
      run  — drive the pipeline end‑to‑end with flags (or interactive mode)

    Tips:
    - Use 'podx COMMAND --help' for details on each tool
    - Use 'podx help --examples' for copy‑paste examples
    - All tools read JSON from stdin and write JSON to stdout so you can pipe them
    """
    pass


def _build_pipeline_config(
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
    preset: Optional[str],
    align: bool,
    preprocess: bool,
    restore: bool,
    diarize: bool,
    deepcast: bool,
    workflow: Optional[str],
    fidelity: Optional[str],
    dual: bool,
    no_consensus: bool,
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
) -> dict:
    """Build pipeline configuration from CLI arguments.

    Applies preset transformations (--full, --workflow, --fidelity) to CLI flags
    and returns a configuration dictionary ready for pipeline execution.

    Args:
        All CLI arguments from run() function

    Returns:
        Configuration dictionary with processed flags
    """
    # Start with all arguments in a dict (will be modified by presets)
    config = {
        "show": show,
        "rss_url": rss_url,
        "youtube_url": youtube_url,
        "date": date,
        "title_contains": title_contains,
        "workdir": workdir,
        "fmt": fmt,
        "model": model,
        "compute": compute,
        "asr_provider": asr_provider,
        "preset": preset,
        "align": align,
        "preprocess": preprocess,
        "restore": restore,
        "diarize": diarize,
        "deepcast": deepcast,
        "dual": dual,
        "no_consensus": no_consensus,
        "deepcast_model": deepcast_model,
        "deepcast_temp": deepcast_temp,
        "extract_markdown": extract_markdown,
        "deepcast_pdf": deepcast_pdf,
        "notion": notion,
        "notion_db": notion_db,
        "podcast_prop": podcast_prop,
        "date_prop": date_prop,
        "episode_prop": episode_prop,
        "model_prop": model_prop,
        "asr_prop": asr_prop,
        "append_content": append_content,
        "verbose": verbose,
        "clean": clean,
        "no_keep_audio": no_keep_audio,
        "yaml_analysis_type": None,  # Will be set by interactive mode or workflow
    }

    # Handle convenience --full flag
    if full:
        config["align"] = True
        config["deepcast"] = True
        config["extract_markdown"] = True
        config["notion"] = True

    # Map --workflow presets first (can be combined with fidelity)
    if workflow:
        from .utils import apply_workflow_preset

        workflow_flags = apply_workflow_preset(workflow)
        config["align"] = workflow_flags.get("align", config["align"])
        config["diarize"] = workflow_flags.get("diarize", config["diarize"])
        config["deepcast"] = workflow_flags.get("deepcast", config["deepcast"])
        config["extract_markdown"] = workflow_flags.get(
            "extract_markdown", config["extract_markdown"]
        )
        config["notion"] = workflow_flags.get("notion", config["notion"])

    # Map --fidelity to flags (lowest→highest)
    # 1: deepcast only (use latest transcript)
    # 2: recall + preprocess + restore + deepcast
    # 3: precision + preprocess + restore + deepcast
    # 4: balanced + preprocess + restore + deepcast
    # 5: dual (precision+recall) + preprocess + restore + deepcast
    if fidelity:
        from .utils import apply_fidelity_preset

        fid_flags = apply_fidelity_preset(fidelity, preset, interactive=False)
        config["align"] = fid_flags.get("align", config["align"])
        config["diarize"] = fid_flags.get("diarize", config["diarize"])
        config["preprocess"] = fid_flags.get("preprocess", config["preprocess"])
        config["restore"] = fid_flags.get("restore", config["restore"])
        config["deepcast"] = fid_flags.get("deepcast", config["deepcast"])
        config["dual"] = fid_flags.get("dual", config["dual"])
        config["preset"] = fid_flags.get("preset", config["preset"])

    return config


def _execute_fetch(
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
        return interactive_mode_meta, interactive_mode_wd

    # 2. YouTube URL mode
    if config.get("youtube_url"):
        from .youtube import (
            get_youtube_metadata,
            is_youtube_url,
        )

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
            f"YouTube metadata fetched: {meta.get('episode_title', 'Unknown')[:80]}"
        )

        # Note: YouTube audio will be downloaded after workdir is created
        # (handled by run() function after _execute_fetch returns)

    # 3. RSS/Podcast mode
    else:
        fetch_cmd = ["podx-fetch"]
        if config.get("show"):
            fetch_cmd.extend(["--show", config["show"]])
        elif config.get("rss_url"):
            fetch_cmd.extend(["--rss-url", config["rss_url"]])
        else:
            raise ValidationError(
                "Either --show, --rss-url, or --youtube-url must be provided."
            )

        if config.get("date"):
            fetch_cmd.extend(["--date", config["date"]])
        if config.get("title_contains"):
            fetch_cmd.extend(["--title-contains", config["title_contains"]])

        # Run fetch first to get metadata
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

    # 4. Apply podcast-specific configuration from YAML/JSON
    from .utils import apply_podcast_config

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
    config["align"] = config_result["align"]
    config["diarize"] = config_result["diarize"]
    config["deepcast"] = config_result["deepcast"]
    config["extract_markdown"] = config_result["extract_markdown"]
    config["notion"] = config_result["notion"]
    config["deepcast_model"] = config_result.get("deepcast_model", config["deepcast_model"])
    config["deepcast_temp"] = config_result.get("deepcast_temp", config["deepcast_temp"])
    config["yaml_analysis_type"] = config_result.get("analysis_type")

    # 5. Determine working directory
    if config.get("workdir"):
        wd = config["workdir"]
    else:
        from .fetch import _generate_workdir

        show = meta.get("show", "Unknown Show")
        episode_date = meta.get("episode_published") or config.get("date") or "unknown"
        wd = _generate_workdir(show, episode_date)

    return meta, wd


def _handle_interactive_mode(config: dict, scan_dir: Path, console) -> tuple[dict, Path]:
    """Handle interactive episode selection and configuration.

    Displays rich table UI for episode selection, prompts for fidelity level,
    model selection, and option toggles. Modifies config dict in place.

    Args:
        config: Pipeline configuration dictionary (modified in place)
        scan_dir: Directory to scan for episodes
        console: Rich console instance

    Returns:
        Tuple of (episode_metadata, working_directory)

    Raises:
        SystemExit: If user cancels selection
    """
    from .ui import Confirmation, select_deepcast_type, select_episode_interactive, select_fidelity_interactive
    from .utils import apply_fidelity_preset

    # 1. Episode selection
    selected, meta = select_episode_interactive(
        scan_dir=scan_dir,
        show_filter=config["show"],
        console=console,
        run_passthrough_fn=_run_passthrough,
    )

    # 2. Fidelity choice with interactive mapping
    from rich.panel import Panel

    fidelity_level, fid_flags = select_fidelity_interactive(
        console=console,
        preset=config.get("preset"),
        apply_fidelity_fn=apply_fidelity_preset,
    )

    # Update config with fidelity flags
    config["align"] = fid_flags.get("align", config["align"])
    config["diarize"] = fid_flags.get("diarize", config["diarize"])
    config["preprocess"] = fid_flags.get("preprocess", config["preprocess"])
    config["restore"] = fid_flags.get("restore", config["restore"])
    config["deepcast"] = fid_flags.get("deepcast", config["deepcast"])
    config["dual"] = fid_flags.get("dual", config["dual"])
    config["preset"] = fid_flags.get("preset", config["preset"])

    # Show resulting flags (yes/no) before overrides
    def yn(val: bool) -> str:
        return "yes" if val else "no"

    summary = (
        f"preset={config['preset'] or '-'}  align={yn(config['align'])}  "
        f"diarize={yn(config['diarize'])}  preprocess={yn(config['preprocess'])}  "
        f"restore={yn(config['restore'])}  deepcast={yn(config['deepcast'])}  "
        f"dual={yn(config['dual'])}"
    )
    console.print(Panel(summary, title="Preset Applied", border_style="green"))

    # 3. Model selection prompts
    # Only prompt for ASR if we'll transcribe (dual or preset set or no transcripts)
    will_transcribe = (
        config["dual"] or config.get("preset") is not None or not any(selected.get("transcripts"))
    )
    if will_transcribe:
        prompt_asr = input(
            f"\nASR model (Enter to keep '{config['model']}', or type e.g. large-v3, small.en; Q=cancel): "
        ).strip()
        if prompt_asr.upper() in {"Q", "QUIT", "EXIT"}:
            raise SystemExit(0)
        if prompt_asr:
            config["model"] = prompt_asr

    # Only prompt for AI if deepcast will run
    if config["deepcast"] or config["dual"]:
        prompt_ai = input(
            f"AI model for deepcast (Enter to keep '{config['deepcast_model']}', Q=cancel): "
        ).strip()
        if prompt_ai.upper() in {"Q", "QUIT", "EXIT"}:
            raise SystemExit(0)
        if prompt_ai:
            config["deepcast_model"] = prompt_ai

    # 4. Options panel: toggle steps and outputs
    console.print(
        Panel(
            "Adjust options below (Enter keeps current): Q cancels",
            title="Options",
            border_style="blue",
        )
    )
    config["align"] = Confirmation.yes_no("Align (WhisperX)", config["align"])
    config["diarize"] = Confirmation.yes_no("Diarize (speaker labels)", config["diarize"])
    config["preprocess"] = Confirmation.yes_no("Preprocess (merge/normalize)", config["preprocess"])
    config["restore"] = (
        Confirmation.yes_no("Semantic restore (LLM)", config["restore"])
        if config["preprocess"]
        else config["restore"]
    )
    config["deepcast"] = Confirmation.yes_no("Deepcast (AI analysis)", config["deepcast"])

    # Only prompt for Dual mode when fidelity didn't already decide it
    if fidelity_level not in {"5", "1", "2", "3", "4"}:
        config["dual"] = Confirmation.yes_no("Dual mode (precision+recall)", config["dual"])

    config["extract_markdown"] = Confirmation.yes_no("Save Markdown file", config["extract_markdown"])
    config["deepcast_pdf"] = Confirmation.yes_no("Also render PDF (pandoc)", config["deepcast_pdf"])

    # 5. Deepcast type selection
    chosen_type = config.get("yaml_analysis_type")
    if config["deepcast"] or config["dual"]:
        chosen_type = select_deepcast_type(console, default_type=chosen_type)

    # 6. Pipeline preview
    stages = ["fetch", "transcode", "transcribe"]
    if config["align"]:
        stages.append("align")
    if config["diarize"]:
        stages.append("diarize")
    if config["preprocess"]:
        stages.append("preprocess" + ("+restore" if config["restore"] else ""))
    if config["deepcast"]:
        stages.append("deepcast")
    if config["dual"]:
        stages.append("agreement" + ("+consensus" if not config["no_consensus"] else ""))

    outputs = []
    if config["extract_markdown"]:
        outputs.append("markdown")
    if config["deepcast_pdf"]:
        outputs.append("pdf")

    preview = (
        f"Pipeline: {' → '.join(stages)}\n"
        f"ASR={config['model']} preset={config['preset'] or '-'} dual={yn(config['dual'])} "
        f"align={yn(config['align'])} diarize={yn(config['diarize'])} "
        f"preprocess={yn(config['preprocess'])} restore={yn(config['restore'])}\n"
        f"AI={config['deepcast_model']} type={chosen_type or '-'} outputs={','.join(outputs) or '-'}"
    )

    # Cost estimate (best-effort)
    try:
        from .deepcast import estimate_deepcast_cost
        from .model_catalog import load_model_catalog

        provider = (
            "openai"
            if config["deepcast_model"].startswith("gpt") or "-" in config["deepcast_model"]
            else "anthropic"
        )
        sel_dir = selected.get("directory") if isinstance(selected, dict) else None
        latest_path = (
            (sel_dir / "latest.json")
            if sel_dir and (sel_dir / "latest.json").exists()
            else None
        )
        if latest_path:
            import json

            transcript_json = json.loads(latest_path.read_text(encoding="utf-8"))
            catalog = load_model_catalog(refresh=False)
            est = estimate_deepcast_cost(
                transcript_json, provider, config["deepcast_model"], catalog
            )
            preview += f"\nEstimated cost: ${est.total_usd:.2f}  (in≈{est.input_tokens:,} tok, out≈{est.output_tokens:,} tok)"
        else:
            preview += "\nEstimated cost: (no transcript yet; will compute after transcribe)"
    except Exception:
        pass

    console.print(Panel(preview, title="Preview", border_style="green"))

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
    "--preset",
    type=click.Choice(["balanced", "precision", "recall"]),
    default=None,
    help="High-level decoding preset for transcribe",
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
    "--preprocess/--no-preprocess",
    default=False,
    help="Run preprocessing (merge/normalize) before alignment/deepcast",
)
@click.option(
    "--restore/--no-restore",
    default=False,
    help="When preprocessing, attempt semantic restore using an LLM",
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
    "--workflow",
    type=click.Choice(["quick", "analyze", "publish"]),
    default=None,
    help="Preconfigured workflow: quick(fetch+transcribe), analyze(transcribe+align+deepcast), publish(full pipeline)",
)
@click.option(
    "--fidelity",
    type=click.Choice(["5", "4", "3", "2", "1"]),
    default=None,
    help="Fidelity 1-5: 1=deepcast only, 2=recall+preprocess+restore+deepcast, 3=precision+preprocess+restore+deepcast, 4=balanced+preprocess+restore+deepcast, 5=dual (precision+recall)+preprocess+restore+deepcast",
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
    "--dual",
    is_flag=True,
    help="Run precision+recall QA: two ASR tracks (precision & recall) + preprocess(+restore) + deepcast both + agreement",
)
@click.option(
    "--no-consensus",
    is_flag=True,
    help="In dual mode, skip consensus merge step",
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
    youtube_url: Optional[str],
    date: Optional[str],
    title_contains: Optional[str],
    workdir: Optional[Path],
    fmt: str,
    model: str,
    compute: str,
    asr_provider: str,
    preset: str | None,
    align: bool,
    preprocess: bool,
    restore: bool,
    diarize: bool,
    deepcast: bool,
    workflow: str | None,
    fidelity: str | None,
    dual: bool,
    no_consensus: bool,
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

    Pipeline Flow:
        1. Source Selection: Fetch from RSS, YouTube, or interactive browser
        2. Audio Processing: Transcode to target format
        3. Transcription: ASR with optional dual-track QA (precision + recall)
        4. Enhancement: Alignment, diarization, preprocessing
        5. Analysis: AI-powered deepcast with configurable types
        6. Export: Markdown, PDF, and format conversions
        7. Publication: Optional Notion upload

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
        workflow: Workflow preset (quick/analyze/publish)
        fidelity: Fidelity level 1-5 (1=fastest, 5=best quality)
        dual: Enable dual QA mode (precision + recall)
        no_consensus: Skip consensus generation in dual mode
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
        preset=preset,
        align=align,
        preprocess=preprocess,
        restore=restore,
        diarize=diarize,
        deepcast=deepcast,
        workflow=workflow,
        fidelity=fidelity,
        dual=dual,
        no_consensus=no_consensus,
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

    # Unpack config to local variables (for existing pipeline code compatibility)
    show = config["show"]
    rss_url = config["rss_url"]
    youtube_url = config["youtube_url"]
    date = config["date"]
    title_contains = config["title_contains"]
    workdir = config["workdir"]
    fmt = config["fmt"]
    model = config["model"]
    compute = config["compute"]
    asr_provider = config["asr_provider"]
    preset = config["preset"]
    align = config["align"]
    preprocess = config["preprocess"]
    restore = config["restore"]
    diarize = config["diarize"]
    deepcast = config["deepcast"]
    dual = config["dual"]
    no_consensus = config["no_consensus"]
    deepcast_model = config["deepcast_model"]
    deepcast_temp = config["deepcast_temp"]
    extract_markdown = config["extract_markdown"]
    deepcast_pdf = config["deepcast_pdf"]
    notion = config["notion"]
    notion_db = config["notion_db"]
    podcast_prop = config["podcast_prop"]
    date_prop = config["date_prop"]
    episode_prop = config["episode_prop"]
    model_prop = config["model_prop"]
    asr_prop = config["asr_prop"]
    append_content = config["append_content"]
    verbose = config["verbose"]
    clean = config["clean"]
    no_keep_audio = config["no_keep_audio"]
    yaml_analysis_type = config["yaml_analysis_type"]

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
            from .ui import make_console

            console = make_console()
            interactive_meta, interactive_wd = _handle_interactive_mode(config, scan_dir, console)

            # Update local variables from modified config
            model = config["model"]
            deepcast_model = config["deepcast_model"]
            align = config["align"]
            diarize = config["diarize"]
            preprocess = config["preprocess"]
            restore = config["restore"]
            deepcast = config["deepcast"]
            dual = config["dual"]
            preset = config["preset"]
            extract_markdown = config["extract_markdown"]
            deepcast_pdf = config["deepcast_pdf"]
            yaml_analysis_type = config["yaml_analysis_type"]

        # 3. Fetch episode metadata and determine working directory
        meta, wd = _execute_fetch(
            config=config,
            interactive_mode_meta=interactive_meta,
            interactive_mode_wd=interactive_wd,
            progress=progress,
            verbose=verbose,
        )

        # Update local variables from podcast-specific config overrides
        align = config["align"]
        diarize = config["diarize"]
        deepcast = config["deepcast"]
        extract_markdown = config["extract_markdown"]
        notion = config["notion"]
        deepcast_model = config["deepcast_model"]
        deepcast_temp = config["deepcast_temp"]
        yaml_analysis_type = config["yaml_analysis_type"]

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

        # Working directory determined by _execute_fetch()
        wd.mkdir(parents=True, exist_ok=True)

        # For YouTube URLs, now do the full fetch with proper workdir
        if youtube_url:
            from .youtube import fetch_youtube_episode

            progress.start_step("Downloading YouTube audio")
            meta = fetch_youtube_episode(youtube_url, wd)
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

        # 3) TRANSCRIBE → transcript-{model}.json (or dual precision/recall)
        # Prefer JSON content over filename to determine asr_model
        from .utils import discover_transcripts, sanitize_model_name

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

        if not dual and transcript_file.exists():
            # Use existing transcript for this specific model
            logger.info(
                f"Found existing transcript for model {model}, skipping transcription"
            )
            base = json.loads(transcript_file.read_text())
            progress.complete_step(
                f"Using existing transcript ({model}) - {len(base.get('segments', []))} segments",
                0,
            )
        elif not dual and existing_transcripts:
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
            if not dual:
                # Single track transcription
                progress.start_step(f"Transcribing with {model} model")
                step_start = time.time()
                transcribe_cmd = ["podx-transcribe", "--model", model, "--compute", compute]
                if asr_provider and asr_provider != "auto":
                    transcribe_cmd += ["--asr-provider", asr_provider]
                if preset:
                    transcribe_cmd += ["--preset", preset]
                base = _run(
                    transcribe_cmd,
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
            else:
                # Dual QA: precision & recall tracks
                progress.start_step(f"Dual QA: transcribing precision & recall with {model}")
                step_start = time.time()
                safe_model = sanitize_model_name(model)
                # Precision (resume if exists)
                t_prec = wd / f"transcript-{safe_model}-precision.json"
                if t_prec.exists():
                    prec = json.loads(t_prec.read_text())
                else:
                    cmd_prec = [
                        "podx-transcribe", "--model", model, "--compute", compute,
                        "--preset", "precision",
                    ]
                    if asr_provider and asr_provider != "auto":
                        cmd_prec += ["--asr-provider", asr_provider]
                    prec = _run(cmd_prec, stdin_payload=audio, verbose=verbose, save_to=t_prec)

                # Recall (resume if exists)
                t_rec = wd / f"transcript-{safe_model}-recall.json"
                if t_rec.exists():
                    rec = json.loads(t_rec.read_text())
                else:
                    cmd_rec = [
                        "podx-transcribe", "--model", model, "--compute", compute,
                        "--preset", "recall",
                    ]
                    if asr_provider and asr_provider != "auto":
                        cmd_rec += ["--asr-provider", asr_provider]
                    rec = _run(cmd_rec, stdin_payload=audio, verbose=verbose, save_to=t_rec)

                step_duration = time.time() - step_start
                progress.complete_step(
                    f"Dual transcription completed (precision: {len(prec.get('segments', []))} segs; recall: {len(rec.get('segments', []))} segs)",
                    step_duration,
                )
                # Set latest to recall by default
                latest = rec
                latest_name = f"transcript-{safe_model}-recall"

        if not dual:
            latest = base
            latest_name = f"transcript-{base.get('asr_model', model)}"

        # 4) PREPROCESS (optional or implied by --dual) → transcript-preprocessed-*.json
        if preprocess or dual:
            from .utils import build_preprocess_command

            progress.start_step("Preprocessing transcript (merge/normalize)")
            step_start = time.time()

            if dual:
                # Preprocess both precision & recall
                safe_model = sanitize_model_name(model)
                t_prec = wd / f"transcript-{safe_model}-precision.json"
                t_rec = wd / f"transcript-{safe_model}-recall.json"
                pre_prec = wd / f"transcript-preprocessed-{safe_model}-precision.json"
                pre_rec = wd / f"transcript-preprocessed-{safe_model}-recall.json"

                _ = _run(
                    build_preprocess_command(pre_prec, restore) + ["--input", str(t_prec)],
                    stdin_payload=None,
                    verbose=verbose,
                    save_to=pre_prec,
                )
                out_rec = _run(
                    build_preprocess_command(pre_rec, restore) + ["--input", str(t_rec)],
                    stdin_payload=None,
                    verbose=verbose,
                    save_to=pre_rec,
                )
                latest = out_rec
                latest_name = f"transcript-preprocessed-{safe_model}-recall"
            else:
                # Single-track: preprocess the latest transcript
                used_model = (latest or {}).get("asr_model", model) if isinstance(latest, dict) else model
                pre_file = wd / f"transcript-preprocessed-{sanitize_model_name(used_model)}.json"
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
        else:
            latest = base
            latest_name = f"transcript-{base.get('asr_model', model)}"

        # 5) ALIGN (optional) → transcript-aligned-{model}.json
        # In dual mode, we still align the currently-latest transcript (per selected track above).
        if align:
            # Get model from base transcript
            used_model = latest.get("asr_model", model)
            aligned_file = wd / f"transcript-aligned-{sanitize_model_name(used_model)}.json"

            # Also check legacy filenames
            legacy_aligned_new = wd / f"aligned-transcript-{used_model}.json"
            legacy_aligned = wd / "aligned-transcript.json"
            if aligned_file.exists():
                logger.info(
                    f"Found existing aligned transcript ({used_model}), skipping alignment"
                )
                aligned = json.loads(aligned_file.read_text())
                progress.complete_step(
                    f"Using existing aligned transcript ({used_model})", 0
                )
                latest = aligned
                latest_name = f"transcript-aligned-{used_model}"
            elif legacy_aligned_new.exists():
                logger.info(f"Found existing legacy aligned transcript ({used_model}), using it")
                aligned = json.loads(legacy_aligned_new.read_text())
                progress.complete_step("Using existing aligned transcript", 0)
                latest = aligned
                latest_name = f"transcript-aligned-{used_model}"
            elif legacy_aligned.exists():
                logger.info("Found existing legacy aligned transcript, using it")
                aligned = json.loads(legacy_aligned.read_text())
                progress.complete_step("Using existing aligned transcript", 0)
                latest = aligned
                latest_name = "transcript-aligned"
            else:
                progress.start_step("Aligning transcript with audio")
                step_start = time.time()
                aligned = _run(
                    ["podx-align"],  # Audio path comes from transcript JSON
                    stdin_payload=latest,
                    verbose=verbose,
                    save_to=aligned_file,
                    label=None,  # Progress handles the display
                )
                step_duration = time.time() - step_start
                progress.complete_step("Audio alignment completed", step_duration)
                latest = aligned
                latest_name = f"transcript-aligned-{used_model}"

        # 6) DIARIZE (optional) → transcript-diarized-{model}.json
        # In dual mode, we diarize the currently-latest transcript as well.
        if diarize:
            # Get model from latest transcript
            used_model = latest.get("asr_model", model)
            diarized_file = wd / f"transcript-diarized-{sanitize_model_name(used_model)}.json"

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
                logger.info(f"Found existing legacy diarized transcript ({used_model}), using it")
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
                    click.secho(
                        f"Debug: Passing {latest_name} JSON to diarize with {len(latest.get('segments', []))} segments",
                        fg="yellow",
                    )
                diar = _run(
                    ["podx-diarize"],  # Audio path comes from aligned transcript JSON
                    stdin_payload=latest,
                    verbose=verbose,
                    save_to=diarized_file,
                    label=None,  # Progress handles the display
                )
                step_duration = time.time() - step_start
                progress.complete_step("Speaker diarization completed", step_duration)
                latest = diar
                latest_name = f"transcript-diarized-{used_model}"

        # Always keep a pointer to the latest JSON/SRT/TXT for convenience
        (wd / "latest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")

        # quick TXT/SRT from whatever we have (prefer diarized/aligned if produced)
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

        # 7) DEEPCAST (optional) or implied by dual → deepcast for one or both
        if deepcast or dual:
            # Use model-specific filenames to allow multiple analyses
            model_suffix = deepcast_model.replace(".", "_").replace("-", "_")
            json_out = wd / f"deepcast-brief-{model_suffix}.json"
            md_out = wd / f"deepcast-brief-{model_suffix}.md"

            if json_out.exists() and not dual:
                logger.info("Found existing deepcast analysis, skipping AI analysis")
                progress.complete_step("Using existing AI analysis", 0)
                results.update({"deepcast_json": str(json_out)})
                if extract_markdown and md_out.exists():
                    results.update({"deepcast_md": str(md_out)})
            else:
                if not dual:
                    # Single-track deepcast always reads the latest processed transcript
                    from .utils import build_deepcast_command

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
                else:
                    # Dual: deepcast precision & recall (requires preprocessed precision/recall inputs)
                    from .utils import build_deepcast_command

                    progress.start_step(f"Analyzing precision & recall with {deepcast_model}")
                    step_start = time.time()
                    safe_model = sanitize_model_name(model)
                    pre_prec = wd / f"transcript-preprocessed-{safe_model}-precision.json"
                    pre_rec = wd / f"transcript-preprocessed-{safe_model}-recall.json"
                    meta_file = wd / "episode-meta.json"

                    if not pre_prec.exists() or not pre_rec.exists():
                        raise ValidationError(
                            "Dual deepcast requires preprocessed precision/recall transcripts; rerun with preprocess enabled or Fidelity 5."
                        )

                    # Precision analysis
                    dc_prec = wd / f"deepcast-{safe_model}-{deepcast_model.replace('.', '_')}-precision.json"
                    cmd_prec = build_deepcast_command(
                        input_path=pre_prec,
                        output_path=dc_prec,
                        model=deepcast_model,
                        temperature=deepcast_temp,
                        meta_path=meta_file,
                        analysis_type=yaml_analysis_type,
                        extract_markdown=extract_markdown,
                        generate_pdf=deepcast_pdf,
                    )
                    _run(cmd_prec, verbose=verbose, save_to=None, label=None)

                    # Recall analysis
                    dc_rec = wd / f"deepcast-{safe_model}-{deepcast_model.replace('.', '_')}-recall.json"
                    cmd_rec = build_deepcast_command(
                        input_path=pre_rec,
                        output_path=dc_rec,
                        model=deepcast_model,
                        temperature=deepcast_temp,
                        meta_path=meta_file,
                        analysis_type=yaml_analysis_type,
                        extract_markdown=extract_markdown,
                        generate_pdf=deepcast_pdf,
                    )
                    _run(cmd_rec, verbose=verbose, save_to=None, label=None)
                    step_duration = time.time() - step_start
                    progress.complete_step("Dual deepcast analyses completed", step_duration)
                    results.update({
                        "deepcast_precision": str(dc_prec),
                        "deepcast_recall": str(dc_rec),
                    })

                    # Agreement
                    progress.start_step("Computing agreement between analyses")
                    agr_out = wd / f"agreement-{safe_model}-{deepcast_model.replace('.', '_')}.json"
                    _run(
                        ["podx-agreement", "--a", str(dc_prec), "--b", str(dc_rec), "--model", deepcast_model],
                        verbose=verbose,
                        save_to=agr_out,
                    )
                    progress.complete_step("Agreement computed", 0)
                    results.update({"agreement": str(agr_out)})

                    # Consensus (unless disabled)
                    if not no_consensus:
                        progress.start_step("Merging consensus output")
                        cons_out = wd / f"consensus-{safe_model}-{deepcast_model.replace('.', '_')}.json"
                        _run(
                            [
                                "podx-consensus",
                                "--precision",
                                str(dc_prec),
                                "--recall",
                                str(dc_rec),
                                "--agreement",
                                str(agr_out),
                                "--output",
                                str(cons_out),
                            ],
                            verbose=verbose,
                            save_to=cons_out,
                        )
                        progress.complete_step("Consensus created", 0)
                        results.update({"consensus": str(cons_out)})

        # Final export step (write exported-<timestamp>.* from consensus or selected track)
        try:
            export_source_path = None
            export_track = None
            if dual and not no_consensus:
                cons = results.get("consensus")
                if cons and Path(cons).exists():
                    export_source_path = Path(cons)
                    export_track = "consensus"
            if export_source_path is None:
                single = results.get("deepcast_json")
                if single and Path(single).exists():
                    export_source_path = Path(single)
                    export_track = (preset or "balanced") if preset else "single"
                else:
                    for key, trk in [("deepcast_recall", "recall"), ("deepcast_precision", "precision")]:
                        p = results.get(key)
                        if p and Path(p).exists():
                            export_source_path = Path(p)
                            export_track = trk
                            break
            if export_source_path and export_source_path.exists():
                data = json.loads(export_source_path.read_text(encoding="utf-8"))
                # Use unified exporter (handles deepcast and consensus JSON, and PDF auto-install)
                try:
                    md_path, pdf_path = export_from_deepcast_json(data, wd, deepcast_pdf, track_hint=export_track)
                    results["exported_md"] = str(md_path)
                    if pdf_path is not None:
                        results["exported_pdf"] = str(pdf_path)
                except Exception:
                    pass
        except Exception:
            pass

        # 7) NOTION (optional) — requires DB id
        if notion and not dual:
            if not notion_db:
                raise SystemExit(
                    "Please pass --db or set NOTION_DB_ID environment variable"
                )

            progress.start_step("Uploading to Notion")
            step_start = time.time()
            # Prefer exported.md if available, else model-specific deepcast outputs, fallback to latest.txt
            model_suffix = deepcast_model.replace(".", "_").replace("-", "_")
            exported_md = Path(results.get("exported_md", "")) if results.get("exported_md") else None
            model_specific_md = wd / f"deepcast-brief-{model_suffix}.md"
            model_specific_json = wd / f"deepcast-brief-{model_suffix}.json"

            # If exported exists, use it directly
            if exported_md and exported_md.exists():
                md_path = str(exported_md)
                json_path = (
                    str(model_specific_json) if model_specific_json.exists() else None
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
                    "--model-prop",
                    model_prop,
                    "--asr-prop",
                    asr_prop,
                    "--deepcast-model",
                    deepcast_model,
                    "--asr-model",
                    model,
                ]
                if json_path:
                    cmd += ["--json", json_path]
            else:
                # Find any deepcast files if model-specific ones don't exist
                # Check for both new and legacy formats
                deepcast_files = list(wd.glob("deepcast-*.md"))
                fallback_md = deepcast_files[0] if deepcast_files else None

            # Prefer unified JSON mode if no separate markdown file exists
            if model_specific_json.exists() and not model_specific_md.exists():
                # Use unified JSON mode (deepcast JSON contains markdown)
                cmd = [
                    "podx-notion",
                    "--input",
                    str(model_specific_json),
                    "--db",
                    notion_db,
                    "--podcast-prop",
                    podcast_prop,
                    "--date-prop",
                    date_prop,
                    "--episode-prop",
                    episode_prop,
                    "--model-prop",
                    model_prop,
                    "--asr-prop",
                    asr_prop,
                    "--deepcast-model",
                    deepcast_model,
                    "--asr-model",
                    model,  # The ASR model from transcription
                ]
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
                    "--model-prop",
                    model_prop,
                    "--asr-prop",
                    asr_prop,
                    "--deepcast-model",
                    deepcast_model,
                    "--asr-model",
                    model,  # The ASR model from transcription
                ]

                if json_path:
                    cmd += ["--json", json_path]

            if append_content:
                cmd += ["--append-content"]
            # Default is replace, so no flag needed when append_content is False

            _ = _run(
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


## Deprecated: info command has been removed in favor of 'podx list'


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


@main.command("models")
@click.pass_context
def models_cmd(ctx):
    """List AI models with pricing and estimate deepcast cost."""
    import sys

    original_argv = sys.argv.copy()
    sys.argv = ["podx-models"] + sys.argv[2:]
    try:
        from . import models as models_cli
        models_cli.main()
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
    "--preset",
    type=click.Choice(["balanced", "precision", "recall"]),
    default=None,
    help="Decoding preset for transcribe",
)
@click.option(
    "--compute",
    default=lambda: get_config().default_compute,
    type=click.Choice(["int8", "int8_float16", "float16", "float32"]),
    help="Compute type",
)
@click.option("-v", "--verbose", is_flag=True, help="Print interstitial outputs")
def quick(show, rss_url, youtube_url, date, title_contains, model, asr_provider, preset, compute, verbose):
    """Quick workflow: fetch + transcribe only (fastest option)."""
    click.secho("[deprecated] Use: podx run --workflow quick", fg="yellow")
    click.echo("🚀 Running quick transcription workflow (alias of run --workflow quick)...")

    # Use the existing run command but with minimal options
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
        preset=preset,
        verbose=verbose,
        workflow="quick",
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
    "--preset",
    type=click.Choice(["balanced", "precision", "recall"]),
    default=None,
    help="Decoding preset for transcribe",
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
    youtube_url,
    date,
    title_contains,
    model,
    asr_provider,
    preset,
    compute,
    deepcast_model,
    podcast_type,
    verbose,
):
    """Analysis workflow: transcribe + align + AI analysis (recommended)."""
    click.secho("[deprecated] Use: podx run --workflow analyze", fg="yellow")
    click.echo("🤖 Running analysis workflow (alias of run --workflow analyze)...")

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
        preset=preset,
        deepcast_model=deepcast_model,
        verbose=verbose,
        workflow="analyze",
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
    click.secho("[deprecated] Use: podx run --workflow publish", fg="yellow")
    click.echo("📝 Running publishing workflow (alias of run --workflow publish)...")

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
        verbose=verbose,
        workflow="publish",
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


@main.command("list", help="Shim: run podx-list with the given arguments")
@click.argument("args", nargs=-1)
def list_shim(args: tuple[str, ...]):
    import sys
    original_argv = sys.argv.copy()
    sys.argv = ["podx-list", *sys.argv[2:]]
    try:
        from .list import main as list_main
        list_main()
    finally:
        sys.argv = original_argv


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


# Lightweight shims to expose individual tools under the unified `podx` namespace
@main.command("preprocess", help="Shim: run podx-preprocess with the given arguments")
@click.argument("args", nargs=-1)
def preprocess_shim(args: tuple[str, ...]):
    code = _run_passthrough(["podx-preprocess", *args])
    sys.exit(code)


@main.command("agreement", help="Shim: run podx-agreement with the given arguments")
@click.argument("args", nargs=-1)
def agreement_shim(args: tuple[str, ...]):
    code = _run_passthrough(["podx-agreement", *args])
    sys.exit(code)


@main.command("consensus", help="Shim: run podx-consensus with the given arguments")
@click.argument("args", nargs=-1)
def consensus_shim(args: tuple[str, ...]):
    code = _run_passthrough(["podx-consensus", *args])
    sys.exit(code)


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
            if len(db.database_id) > 16
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


if __name__ == "__main__":
    main()
