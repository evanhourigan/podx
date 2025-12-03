"""CLI wrapper for diarize command.

Simplified v4.0 command that operates on episode directories.
"""

import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.core.diarize import (
    DiarizationEngine,
    DiarizationError,
    calculate_chunk_duration,
    calculate_embedding_batch_size,
    estimate_memory_required,
    get_audio_duration,
    get_memory_info,
)
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger
from podx.ui import LiveTimer, select_episode_interactive

logger = get_logger(__name__)
console = Console()


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


@click.command(context_settings={"max_content_width": 120})
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
    Notes:
      - Episode must have transcript.json (run 'podx transcribe' first)
      - Episode must have audio file (audio.wav or audio.mp3)
      - First run downloads ~1GB pyannote model (cached after)
      - Requires HUGGINGFACE_TOKEN environment variable

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
                require="transcript",
                title="Select episode to diarize",
            )
            if not selected:
                console.print("[dim]Selection cancelled[/dim]")
                sys.exit(0)

            path = selected["directory"]

            # Warn if already diarized
            if selected.get("diarized"):
                console.print(
                    "\n[yellow]This episode already has speaker labels.[/yellow]"
                )
                console.print(
                    "[dim]Re-diarizing will overwrite the existing labels.[/dim]"
                )
                try:
                    confirm = input("Continue? [y/N] ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[dim]Cancelled[/dim]")
                    sys.exit(0)
                if confirm not in ("y", "yes"):
                    console.print("[dim]Cancelled[/dim]")
                    sys.exit(0)
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)

    # Resolve path
    episode_dir = path.resolve()
    if episode_dir.is_file():
        episode_dir = episode_dir.parent

    # Find transcript
    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        console.print(f"[red]Error:[/red] No transcript.json found in {episode_dir}")
        console.print("[dim]Run 'podx transcribe' first[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    # Find audio file
    audio_file = _find_audio_file(episode_dir)
    if not audio_file:
        console.print(f"[red]Error:[/red] No audio file found in {episode_dir}")
        sys.exit(ExitCode.USER_ERROR)

    # Load transcript
    try:
        transcript = json.loads(transcript_path.read_text())
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to load transcript: {e}")
        sys.exit(ExitCode.USER_ERROR)

    if "segments" not in transcript:
        console.print("[red]Error:[/red] transcript.json missing 'segments' field")
        sys.exit(ExitCode.USER_ERROR)

    # Block if transcript has been cleaned
    if transcript.get("cleaned"):
        console.print("[red]Error:[/red] This transcript has already been cleaned up.")
        console.print(
            "Diarization requires the raw ASR output to align with the audio."
        )
        console.print(
            "[dim]Re-run 'podx transcribe' first, then 'podx diarize', then 'podx cleanup'.[/dim]"
        )
        sys.exit(ExitCode.USER_ERROR)

    # Get language from transcript
    language = transcript.get("language", "en")

    # Check memory, duration, and chunking requirements
    available_gb, total_gb = get_memory_info()
    batch_size = calculate_embedding_batch_size(available_gb)

    try:
        audio_duration_minutes = get_audio_duration(audio_file)
    except DiarizationError:
        audio_duration_minutes = 0  # Will proceed without duration info

    estimated_memory = estimate_memory_required(audio_duration_minutes)
    chunk_duration, needs_chunking = calculate_chunk_duration(
        available_gb, audio_duration_minutes
    )

    # Display info
    console.print(f"[cyan]Diarizing:[/cyan] {audio_file.name}")
    console.print(f"[cyan]Transcript:[/cyan] {transcript_path.name}")
    if speakers:
        console.print(f"[cyan]Expected speakers:[/cyan] {speakers}")
    else:
        console.print("[cyan]Expected speakers:[/cyan] auto-detect")
    console.print(
        f"[cyan]Memory:[/cyan] {available_gb:.1f} GB available / {total_gb:.1f} GB total"
    )
    if audio_duration_minutes > 0:
        console.print(
            f"[cyan]Audio duration:[/cyan] {audio_duration_minutes:.0f} minutes"
        )
        memory_status = "✓" if not needs_chunking else "✗"
        console.print(
            f"[cyan]Estimated memory:[/cyan] {estimated_memory:.1f} GB {memory_status}"
        )

    # Show chunking warning if needed
    if needs_chunking:
        num_chunks = int((audio_duration_minutes * 60) / (chunk_duration * 60 - 30)) + 1
        console.print()
        console.print("[yellow][!] Chunked diarization required[/yellow]")
        console.print(
            f"    Your system has {available_gb:.1f} GB available, "
            f"but full processing needs ~{estimated_memory:.1f} GB."
        )
        console.print(
            f"    Splitting into {num_chunks} chunks of ~{chunk_duration:.0f} minutes "
            "with speaker re-identification."
        )
        console.print()
        console.print(
            "    [dim]Trade-off: ~2-5% potential speaker matching errors "
            "at chunk boundaries.[/dim]"
        )
        console.print()
        console.print("    [dim]For best results:[/dim]")
        console.print("    [dim]• Close other applications to free memory[/dim]")
        console.print()
    elif batch_size < 32:
        console.print(
            f"[dim]Using reduced batch size ({batch_size}) for memory efficiency[/dim]"
        )

    # Start timer
    timer = LiveTimer("Diarizing")
    timer.start()

    def progress_callback(msg: str) -> None:
        """Update the timer message for step transitions."""
        timer.message = msg

    try:
        engine = DiarizationEngine(
            language=language,
            device=None,  # Auto-detect
            hf_token=os.getenv("HUGGINGFACE_TOKEN"),
            num_speakers=speakers,
            progress_callback=progress_callback,
        )
        # Suppress WhisperX debug output during diarization
        with (
            redirect_stdout(open(os.devnull, "w")),
            redirect_stderr(open(os.devnull, "w")),
        ):
            result = engine.diarize(audio_file, transcript["segments"])

    except DiarizationError as e:
        timer.stop()
        console.print(f"[red]Diarization Error:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)
    except FileNotFoundError as e:
        timer.stop()
        console.print(f"[red]File Not Found:[/red] {e}")
        sys.exit(ExitCode.USER_ERROR)

    # Stop timer
    elapsed = timer.stop()
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
    console.print(f"\n[green]✓ Diarization complete ({minutes}:{seconds:02d})[/green]")
    console.print(f"  Speakers found: {len(speakers_found)}")

    # Show chunking info if it was used
    if hasattr(engine, "_chunking_info") and engine._chunking_info.get(
        "needs_chunking"
    ):
        num_chunks = engine._chunking_info.get("num_chunks", "?")
        console.print(f"  Chunks processed: {num_chunks}")

    console.print(f"  Updated: {transcript_path}")

    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
