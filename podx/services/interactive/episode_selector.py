"""Interactive episode selection and configuration."""

from pathlib import Path
from typing import Any, Dict, Tuple

from rich.panel import Panel


def handle_interactive_mode(
    config: Dict[str, Any], scan_dir: Path, console: Any
) -> Tuple[Dict[str, Any], Path]:
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
    from podx.ui import select_episode_interactive

    # 1. Episode selection
    selected, meta = select_episode_interactive(
        scan_dir=str(scan_dir),
        show_filter=config.get("show"),
        console=console,
    )

    # 2. Interactive configuration panel removed in v4.0.0
    # Just use config as-is
    updated_config = config

    # Merge updated config back
    config.update(updated_config)
    chosen_type = config.get("yaml_analysis_type")

    # 3. Episode metadata display
    from podx.services.orchestration.display import build_episode_metadata_display

    episode_metadata = build_episode_metadata_display(selected, meta, config)
    console.print(Panel(episode_metadata, title="Episode", border_style="cyan"))

    # 4. Pipeline preview
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

    # 5. Final confirmation (strict y/n validation)
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
