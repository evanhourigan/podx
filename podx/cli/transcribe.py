"""CLI wrapper for transcribe command.

Simplified v4.0 command that operates on episode directories.
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional

import click

from podx.config import get_config
from podx.core.transcribe import TranscriptionEngine, TranscriptionError
from podx.domain.exit_codes import ExitCode
from podx.errors import AudioError
from podx.logging import get_logger
from podx.ui import select_episode_interactive

logger = get_logger(__name__)


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


@click.command()
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
    Models:
      Local (free, runs on your machine):
        large-v3          Best quality (default)
        large-v2          Previous best
        medium            Good balance of speed/quality
        base              Fast, lower accuracy
        tiny              Fastest, lowest accuracy

      Cloud (requires API key):
        openai:whisper-1  $0.006/min, requires OPENAI_API_KEY

      HuggingFace (downloads model locally, free):
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
                click.echo("Selection cancelled")
                sys.exit(0)

            path = selected["directory"]
        except KeyboardInterrupt:
            click.echo("\nCancelled")
            sys.exit(0)

    # Resolve path
    episode_dir = path.resolve()
    if episode_dir.is_file():
        episode_dir = episode_dir.parent

    # Find audio file
    audio_file = _find_audio_file(episode_dir)
    if not audio_file:
        click.echo(f"podx transcribe: no audio file found in {episode_dir}", err=True)
        sys.exit(ExitCode.USER_ERROR)

    # Output path
    transcript_path = episode_dir / "transcript.json"

    # Show what we're doing
    click.echo(f"Transcribing: {audio_file.name}")
    click.echo(f"Model: {model}")
    if language != "auto":
        click.echo(f"Language: {language}")

    start_time = time.time()

    try:
        # Parse model to determine provider
        provider = None
        model_name = model
        if ":" in model:
            provider, model_name = model.split(":", 1)

        engine = TranscriptionEngine(
            model=model_name,
            provider=provider,
            compute_type=None,  # Auto-detect
            device=None,  # Auto-detect
        )

        result = engine.transcribe(audio_file, language=language if language != "auto" else None)

    except TranscriptionError as e:
        click.echo(f"podx transcribe: {e}", err=True)
        sys.exit(ExitCode.PROCESSING_ERROR)
    except AudioError as e:
        click.echo(f"podx transcribe: {e}", err=True)
        sys.exit(ExitCode.USER_ERROR)

    # Calculate elapsed time
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Add metadata
    result["audio_path"] = str(audio_file)

    # Save transcript
    transcript_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Show completion
    click.echo(f"Transcription complete ({minutes}:{seconds:02d})")
    click.echo(f"  Segments: {len(result.get('segments', []))}")
    click.echo(f"  Language: {result.get('language', 'unknown')}")
    click.echo(f"  Output: {transcript_path}")

    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
