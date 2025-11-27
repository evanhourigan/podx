"""CLI wrapper for diarize command.

Simplified v4.0 command that operates on episode directories.
"""

import json
import os
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Optional

import click

from podx.core.diarize import DiarizationEngine, DiarizationError
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger
from podx.ui import select_episode_interactive

logger = get_logger(__name__)


def _find_audio_file(directory: Path) -> Optional[Path]:
    """Find audio file in episode directory."""
    for ext in [".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"]:
        audio_file = directory / f"audio{ext}"
        if audio_file.exists():
            return audio_file

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
    "--speakers",
    type=int,
    default=None,
    help="Expected number of speakers (improves accuracy)",
)
def main(path: Optional[Path], speakers: Optional[int]):
    """Add speaker labels to a transcript.

    \b
    Arguments:
      PATH    Episode directory (default: current directory)

    Without PATH, shows interactive episode selection.

    \b
    Requirements:
      - Episode must have transcript.json (run 'podx transcribe' first)
      - Episode must have audio file (audio.wav or audio.mp3)
      - First run downloads ~1GB pyannote model (cached after)
      - Optional: Set HUGGINGFACE_TOKEN for better diarization models

    \b
    Examples:
      podx diarize                              # Interactive selection
      podx diarize ./Show/2024-11-24-ep/        # Direct path
      podx diarize . --speakers 2               # Hint: 2 speakers expected
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

    # Find transcript
    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        click.echo(f"podx diarize: no transcript.json found in {episode_dir}", err=True)
        click.echo("Run 'podx transcribe' first", err=True)
        sys.exit(ExitCode.USER_ERROR)

    # Find audio file
    audio_file = _find_audio_file(episode_dir)
    if not audio_file:
        click.echo(f"podx diarize: no audio file found in {episode_dir}", err=True)
        sys.exit(ExitCode.USER_ERROR)

    # Load transcript
    try:
        transcript = json.loads(transcript_path.read_text())
    except Exception as e:
        click.echo(f"podx diarize: failed to load transcript: {e}", err=True)
        sys.exit(ExitCode.USER_ERROR)

    if "segments" not in transcript:
        click.echo("podx diarize: transcript.json missing 'segments' field", err=True)
        sys.exit(ExitCode.USER_ERROR)

    # Get language from transcript
    language = transcript.get("language", "en")

    # Show what we're doing
    click.echo(f"Diarizing: {audio_file.name}")
    click.echo(f"Transcript: {transcript_path.name}")
    if speakers:
        click.echo(f"Expected speakers: {speakers}")

    start_time = time.time()

    try:
        # Suppress WhisperX debug output
        with (
            redirect_stdout(open(os.devnull, "w")),
            redirect_stderr(open(os.devnull, "w")),
        ):
            engine = DiarizationEngine(
                language=language,
                device=None,  # Auto-detect
                hf_token=os.getenv("HUGGINGFACE_TOKEN"),
                num_speakers=speakers,
            )
            result = engine.diarize(audio_file, transcript["segments"])

    except DiarizationError as e:
        click.echo(f"podx diarize: {e}", err=True)
        sys.exit(ExitCode.PROCESSING_ERROR)
    except FileNotFoundError as e:
        click.echo(f"podx diarize: {e}", err=True)
        sys.exit(ExitCode.USER_ERROR)

    # Calculate elapsed time
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Update transcript with diarization results
    transcript["segments"] = result["segments"]
    transcript["diarized"] = True
    transcript["audio_path"] = str(audio_file)

    # Count speakers
    speakers_found = set()
    for seg in result.get("segments", []):
        if seg.get("speaker"):
            speakers_found.add(seg["speaker"])

    # Save updated transcript
    transcript_path.write_text(
        json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Show completion
    click.echo(f"Diarization complete ({minutes}:{seconds:02d})")
    click.echo(f"  Speakers found: {len(speakers_found)}")
    click.echo(f"  Updated: {transcript_path}")

    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
