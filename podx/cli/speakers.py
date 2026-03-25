"""CLI command for standalone speaker identification.

Decoupled from the cleanup command so speaker maps can be created
or re-applied without running the full cleanup pipeline.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.core.history import record_processing_event
from podx.core.speakers import load_speaker_map, save_speaker_map
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger
from podx.ui import (
    apply_speaker_names,
    identify_speakers_interactive,
    resolve_audio_path,
    select_episode_interactive,
)

logger = get_logger(__name__)
console = Console()


@click.command(context_settings={"max_content_width": 120})
@click.argument("path", type=click.Path(exists=True, path_type=Path), required=False)
@click.option(
    "--reidentify", is_flag=True, help="Re-run identification even if speaker-map.json exists"
)
def main(path: Optional[Path], reidentify: bool) -> None:
    """Identify speakers in a diarized transcript.

    Shows transcript samples for each speaker and prompts for real names.
    Saves the mapping to speaker-map.json so it can be reused.

    \b
    Examples:
      podx speakers                              # Interactive episode selection
      podx speakers ./Show/2024-11-24-ep/        # Direct path
      podx speakers ./ep/ --reidentify           # Re-do identification
    """
    # Resolve episode directory
    if path:
        episode_dir = path if path.is_dir() else path.parent
    else:
        episode_dir = select_episode_interactive()
        if not episode_dir:
            sys.exit(0)

    # Load transcript
    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        console.print(f"[red]Error:[/red] No transcript.json found in {episode_dir}")
        console.print("[dim]Run 'podx transcribe' and 'podx diarize' first[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments = transcript.get("segments", [])
    if not segments:
        console.print("[red]Error:[/red] transcript.json has no segments")
        sys.exit(ExitCode.USER_ERROR)

    # Check for existing speaker map
    existing_map = load_speaker_map(episode_dir)
    if existing_map and not reidentify:
        console.print(f"[green]Speaker map already exists ({len(existing_map)} speakers):[/green]")
        for old, new in existing_map.items():
            console.print(f"  {old} -> {new}")
        console.print("[dim]Use --reidentify to re-do identification[/dim]")
        sys.exit(ExitCode.SUCCESS)

    # Check if transcript has speaker labels at all
    has_speakers = any(seg.get("speaker") for seg in segments)
    if not has_speakers:
        console.print("[yellow]Warning:[/yellow] Transcript has no speaker labels")
        console.print("[dim]Run 'podx diarize' first to add speaker labels[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    # Resolve audio path for playback
    audio_path = resolve_audio_path(episode_dir, transcript.get("audio_path"))

    # Run interactive speaker identification
    try:
        speaker_map = identify_speakers_interactive(segments, audio_path=audio_path)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        sys.exit(0)

    if not speaker_map:
        console.print("[dim]No speakers identified[/dim]")
        sys.exit(ExitCode.SUCCESS)

    # Save speaker map
    map_path = save_speaker_map(episode_dir, speaker_map)
    console.print(f"[green]Saved speaker map to {map_path.name}[/green]")

    # Apply to transcript
    transcript["segments"] = apply_speaker_names(segments, speaker_map)
    transcript_path.write_text(
        json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    console.print(f"[green]Applied {len(speaker_map)} speaker name(s) to transcript.json[/green]")

    # Show mapping
    for old, new in speaker_map.items():
        console.print(f"  {old} -> {new}")

    # Record history
    episode_meta_path = episode_dir / "episode-meta.json"
    show = None
    episode_title = None
    if episode_meta_path.exists():
        meta = json.loads(episode_meta_path.read_text(encoding="utf-8"))
        show = meta.get("show")
        episode_title = meta.get("episode_title")

    record_processing_event(
        episode_dir=episode_dir,
        step="speakers",
        show=show,
        episode_title=episode_title or episode_dir.name,
    )

    sys.exit(ExitCode.SUCCESS)
