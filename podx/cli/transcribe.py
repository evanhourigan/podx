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
from podx.core.history import record_processing_event
from podx.core.transcribe import TranscriptionEngine, TranscriptionError
from podx.domain.exit_codes import ExitCode
from podx.errors import AudioError
from podx.logging import get_logger
from podx.ui import (
    LiveTimer,
    LiveTimerProgressReporter,
    get_asr_models_help,
    get_languages_help,
    prompt_with_help,
    select_episode_interactive,
    show_confirmation,
    validate_asr_model,
    validate_language,
)

logger = get_logger(__name__)
console = Console()

# Sentinel value to detect if option was explicitly passed
_NOT_PROVIDED = object()


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


def _get_default_model() -> str:
    """Get default model from config or fallback."""
    try:
        config_model = get_config().default_asr_model
        if config_model:
            # Add local: prefix for local models if not already prefixed
            if ":" not in config_model:
                config_model = f"local:{config_model}"
            return config_model
    except Exception:
        pass
    return "local:large-v3-turbo"


def _get_default_language() -> str:
    """Get default language from config or fallback."""
    return "auto"


@click.command(context_settings={"max_content_width": 120})
@click.argument(
    "path",
    type=click.Path(exists=True, path_type=Path),
    required=False,
)
@click.option(
    "--model",
    default=None,
    help=f"Transcription model (default: {_get_default_model()})",
)
@click.option(
    "--language",
    default=None,
    help=f"Language code (default: {_get_default_language()})",
)
def main(path: Optional[Path], model: Optional[str], language: Optional[str]):
    """Transcribe audio to text.

    \b
    Arguments:
      PATH    Episode directory (default: current directory)

    Without PATH, shows interactive episode selection.

    \b
    Models - Local (free, runs on your machine):
      local:large-v3-turbo  Best quality, optimized
      local:large-v3        Best quality
      local:large-v2        Previous best
      local:medium          Good balance of speed/quality
      local:base            Fast, lower accuracy
      local:tiny            Fastest, lowest accuracy

    \b
    Models - RunPod Cloud (requires 'podx cloud setup'):
      runpod:large-v3-turbo  ~$0.05/hr, fastest cloud option
      runpod:large-v3        ~$0.05/hr, best quality

    \b
    Models - OpenAI (requires API key):
      openai:whisper-1  $0.006/min, requires OPENAI_API_KEY

    \b
    Models - HuggingFace (downloads locally, free):
      hf:distil-large-v3  Distilled, faster than large-v3

    \b
    Languages:
      auto    Auto-detect language
      en      English
      es      Spanish
      fr      French
      de      German
      ...     (ISO 639-1 two-letter codes)

    \b
    Examples:
      podx transcribe                                # Interactive selection
      podx transcribe ./Show/2024-11-24-ep/          # Direct path
      podx transcribe . --model local:medium         # Current dir, medium model
      podx transcribe ./ep/ --language es            # Spanish transcription
    """
    # Get defaults
    default_model = _get_default_model()
    default_language = _get_default_language()

    # Track if we're in interactive mode (no PATH provided)
    interactive_mode = path is None

    # Interactive mode if no path provided
    if interactive_mode:
        try:
            selected, _ = select_episode_interactive(
                scan_dir=".",
                show_filter=None,
                title="Select episode to transcribe",
            )
            if not selected:
                console.print("[dim]Selection cancelled[/dim]")
                sys.exit(0)

            path = selected["directory"]

            # Warn if already transcribed
            if selected.get("transcribed"):
                console.print("\n[yellow]This episode already has a transcript.[/yellow]")
                console.print("[dim]Re-transcribing will overwrite the existing file.[/dim]")
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

    # Resolve path (path is guaranteed to be set by now - either from arg or interactive)
    assert path is not None
    episode_dir = path.resolve()
    if episode_dir.is_file():
        episode_dir = episode_dir.parent

    # Find audio file
    audio_file = _find_audio_file(episode_dir)
    if not audio_file:
        console.print(f"[red]Error:[/red] No audio file found in {episode_dir}")
        console.print("[dim]Expected: audio.mp3, audio.wav, or similar[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    # Interactive prompts for options (only in interactive mode)
    if interactive_mode:
        # Model prompt/confirmation
        if model is not None:
            show_confirmation("Model", model)
        else:
            model = prompt_with_help(
                help_text=get_asr_models_help(),
                prompt_label="Model",
                default=default_model,
                validator=validate_asr_model,
                error_message="Invalid model. See list above for valid options.",
            )

        # Language prompt/confirmation
        if language is not None:
            show_confirmation("Language", language)
        else:
            language = prompt_with_help(
                help_text=get_languages_help(),
                prompt_label="Language",
                default=default_language,
                validator=validate_language,
                error_message="Invalid language code. Use 'auto' or ISO 639-1 codes.",
            )
    else:
        # Non-interactive: use defaults if not specified
        if model is None:
            model = default_model
        if language is None:
            language = default_language

    # Output path
    transcript_path = episode_dir / "transcript.json"

    # Show what we're doing
    console.print(f"\n[cyan]Transcribing:[/cyan] {audio_file.name}")
    console.print(f"[cyan]Model:[/cyan] {model}")
    if language != "auto":
        console.print(f"[cyan]Language:[/cyan] {language}")

    # Start timer with progress reporter
    timer = LiveTimer("Transcribing")
    progress = LiveTimerProgressReporter(timer)
    timer.start()

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
            progress=progress,
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

    # Set initial state flags
    result["diarized"] = False
    result["cleaned"] = False
    result["restored"] = False

    # Save transcript
    transcript_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # Record history event
    episode_meta = {}
    meta_path = episode_dir / "episode-meta.json"
    if meta_path.exists():
        try:
            episode_meta = json.loads(meta_path.read_text())
        except Exception:
            pass  # Non-fatal

    record_processing_event(
        episode_dir=episode_dir,
        step="transcribe",
        model=model,
        show=episode_meta.get("show"),
        episode_title=episode_meta.get("episode_title", episode_dir.name),
        details={"language": result.get("language", language)},
    )

    # Show completion
    console.print(f"\n[green]✓ Transcription complete ({minutes}:{seconds:02d})[/green]")
    console.print(f"  Segments: {len(result.get('segments', []))}")
    console.print(f"  Language: {result.get('language', 'unknown')}")
    console.print(f"  Output: {transcript_path}")

    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
