"""CLI wrapper for transcribe command.

Simplified v4.0 command that operates on episode directories.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.config import get_config
from podx.core.transcribe import TranscriptionEngine, TranscriptionError
from podx.domain.exit_codes import ExitCode
from podx.errors import AudioError
from podx.logging import get_logger
from podx.ui import LiveTimer, select_episode_interactive

logger = get_logger(__name__)
console = Console()


def _find_audio_file(directory: Path) -> Optional[Path]:
    """Find audio file in episode directory."""
    # Check for standard audio files
    for ext in [".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"]:
        # Check for audio.* pattern first
        audio_file = directory / f"audio{ext}"
        if audio_file.exists():
            return audio_file

    # Fall back to any audio file
    for ext in [".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"]:
        matches = list(directory.glob(f"*{ext}"))
        if matches:
            return matches[0]

    return None


@click.command(context_settings={"max_content_width": 120})
@click.argument(
    "path",
    type=click.Path(exists=True, path_type=Path),
    required=False,
)
@click.option(
    "--model",
    default=lambda: get_config().default_asr_model,
    help="Transcription model (e.g., large-v3, medium, openai:whisper-1)",
)
@click.option(
    "--language",
    default="auto",
    help="Language code (auto, en, es, fr, de, ja, zh, etc.)",
)
def main(path: Optional[Path], model: str, language: str):
    """Transcribe audio to text.

    \b
    Arguments:
      PATH    Episode directory (default: current directory)

    Without PATH, shows interactive episode selection.

    \b
    Models - Local (free, runs on your machine):
      large-v3          Best quality (default)
      large-v2          Previous best
      medium            Good balance of speed/quality
      base              Fast, lower accuracy
      tiny              Fastest, lowest accuracy

    \b
    Models - Cloud (requires API key):
      openai:whisper-1  $0.006/min, requires OPENAI_API_KEY

    \b
    Models - HuggingFace (downloads locally, free):
      hf:distil-large-v3  Distilled, faster than large-v3

    \b
    Examples:
      podx transcribe                           # Interactive selection
      podx transcribe ./Show/2024-11-24-ep/     # Direct path
      podx transcribe . --model medium          # Current dir, medium model
      podx transcribe ./ep/ --language es       # Spanish transcription
    """
    # Interactive mode if no path provided
    if path is None:
        try:
            selected, _ = select_episode_interactive(
                scan_dir=".",
                show_filter=None,
            )
            if not selected:
                console.print("[dim]Selection cancelled[/dim]")
                sys.exit(0)

            path = selected["directory"]
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)

    # Resolve path
    episode_dir = path.resolve()
    if episode_dir.is_file():
        episode_dir = episode_dir.parent

    # Find audio file
    audio_file = _find_audio_file(episode_dir)
    if not audio_file:
        console.print(f"[red]Error:[/red] No audio file found in {episode_dir}")
        console.print("[dim]Expected: audio.mp3, audio.wav, or similar[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    # Output path
    transcript_path = episode_dir / "transcript.json"

    # Show what we're doing
    console.print(f"[cyan]Transcribing:[/cyan] {audio_file.name}")
    console.print(f"[cyan]Model:[/cyan] {model}")
    if language != "auto":
        console.print(f"[cyan]Language:[/cyan] {language}")

    # Start timer
    timer = LiveTimer("Transcribing")
    timer.start()

    try:
        # Parse model to determine provider
        provider = None
        model_name = model
        if ":" in model:
            provider, model_name = model.split(":", 1)

        def progress_callback(msg: str):
            # Update the timer message
            timer.message = msg

        engine = TranscriptionEngine(
            model=model_name,
            provider=provider,
            compute_type=None,  # Auto-detect
            device=None,  # Auto-detect
            progress=progress_callback,
        )

        result = engine.transcribe(audio_file)

    except TranscriptionError as e:
        timer.stop()
        console.print(f"[red]Transcription Error:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)
    except AudioError as e:
        timer.stop()
        console.print(f"[red]Audio Error:[/red] {e}")
        sys.exit(ExitCode.USER_ERROR)

    # Stop timer
    elapsed = timer.stop()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Add metadata
    result["audio_path"] = str(audio_file)

    # Save transcript
    transcript_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Show completion
    console.print(
        f"\n[green]✓ Transcription complete ({minutes}:{seconds:02d})[/green]"
    )
    console.print(f"  Segments: {len(result.get('segments', []))}")
    console.print(f"  Language: {result.get('language', 'unknown')}")
    console.print(f"  Output: {transcript_path}")

    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
