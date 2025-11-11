"""CLI wrapper for transcribe command.

Thin Click wrapper that uses core.transcribe.TranscriptionEngine for actual logic.
Handles CLI arguments, input/output, and interactive mode with progress display.
"""
import json
import sys
from pathlib import Path

import click

from podx.cli.cli_shared import print_json, read_stdin_json
from podx.config import get_config
from podx.core.transcribe import TranscriptionEngine, TranscriptionError
from podx.domain.exit_codes import ExitCode
from podx.errors import AudioError, ValidationError
from podx.logging import get_logger
from podx.schemas import AudioMeta, Transcript
from podx.utils import sanitize_model_name
from podx.validation import validate_output

logger = get_logger(__name__)

# Interactive browser imports (optional)
try:
    import importlib.util

    TEXTUAL_AVAILABLE = importlib.util.find_spec("textual") is not None
except ImportError:
    TEXTUAL_AVAILABLE = False

# Rich console for live timer in interactive mode
try:
    import importlib.util

    RICH_AVAILABLE = importlib.util.find_spec("rich") is not None
except ImportError:
    RICH_AVAILABLE = False

# Shared UI components
try:
    from podx.ui import (
        LiveTimer,
        scan_transcribable_episodes,
        select_episode_for_processing,
    )
except Exception:
    from podx.ui.live_timer import LiveTimer
    from podx.ui.transcribe_browser import scan_transcribable_episodes

    def select_episode_for_processing(*args, **kwargs):
        raise ImportError("UI module not available")


def _truncate_text(text: str, max_length: int = 60) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


@click.command()
@click.option(
    "--model",
    default=lambda: get_config().default_asr_model,
    help=(
        "ASR model (e.g., tiny, base, small, medium, large, large-v2, large-v3, "
        "small.en, medium.en, or prefixed: openai:large-v3-turbo, hf:distil-large-v3)"
    ),
)
@click.option(
    "--asr-provider",
    type=click.Choice(["auto", "local", "openai", "hf"]),
    default="auto",
    help="ASR provider (auto-detect by model prefix/alias if 'auto')",
)
@click.option(
    "--expert",
    is_flag=True,
    help="Show and enable expert decoder flags (for advanced users)",
)
@click.option(
    "--vad-filter/--no-vad",
    default=None,
    help="Enable/disable VAD filtering (default: enabled)",
)
@click.option(
    "--condition-on-previous-text/--no-condition",
    "condition_on_previous_text",
    default=None,
    help="Enable/disable conditioning on previous text (default: enabled)",
)
@click.option(
    "--decode-option",
    multiple=True,
    help="Expert decoder options (key=value format, e.g., beam_size=5)",
)
@click.option(
    "--compute",
    type=click.Choice(["auto", "int8", "int8_float16", "int8_bfloat16", "float16"]),
    default=lambda: get_config().default_compute,
    help="Compute type for faster-whisper (auto=detect optimal for device, local provider only)",
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read AudioMeta JSON from file instead of stdin",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save Transcript JSON to file (also prints to stdout)",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive browser to select episodes and models for transcription",
)
@click.option(
    "--scan-dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Directory to scan for episodes (default: current directory)",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output structured JSON (suppresses Rich formatting)",
)
@click.option(
    "--progress-json",
    is_flag=True,
    help="Output progress updates as newline-delimited JSON",
)
@validate_output(Transcript)
def main(
    model,
    asr_provider,
    expert,
    vad_filter,
    condition_on_previous_text,
    decode_option,
    compute,
    input,
    output,
    interactive,
    scan_dir,
    json_output,
    progress_json,
):
    """
    Read AudioMeta JSON on stdin -> run faster-whisper -> print Transcript JSON to stdout.

    With --interactive, browse episodes and select one to transcribe.
    """
    # Handle interactive mode
    if interactive:
        if not TEXTUAL_AVAILABLE:
            if json_output:
                print(
                    json.dumps(
                        {
                            "error": "Interactive mode requires textual library",
                            "install": "pip install textual",
                        }
                    )
                )
            else:
                from rich.console import Console
                console = Console()
                console.print(
                    "[red]Error:[/red] Interactive mode requires textual library. "
                    "Install with: [cyan]pip install textual[/cyan]"
                )
            sys.exit(ExitCode.USER_ERROR)

        # Suppress logging before TUI starts
        from podx.logging import restore_logging, suppress_logging

        suppress_logging()

        try:
            # Browse and select episode and ASR model using integrated TUI
            logger.info(f"Scanning for episodes in: {scan_dir}")
            result = select_episode_for_processing(
                scan_dir=Path(scan_dir),
                title="Select Episode for Transcription",
                episode_scanner=scan_transcribable_episodes,
                show_model_selection=True,
            )

            if not result:
                restore_logging()
                logger.info("User cancelled episode/model selection")
                print("❌ Selection cancelled")
                sys.exit(0)

            # Unpack result - should be (episode, model) tuple
            if isinstance(result, tuple) and len(result) == 2:
                selected, selected_model = result
            else:
                restore_logging()
                logger.error("Unexpected result format from episode browser")
                print("❌ Internal error: unexpected result format")
                sys.exit(1)

        finally:
            # Restore logging after TUI exits
            restore_logging()

        # Override model parameter with user selection
        model = selected_model

        # Use selected episode's audio path
        audio = selected["audio_path"]
        episode_dir = selected["directory"]

        # Force output to transcript-{safe_model}.json in episode directory
        safe_model = sanitize_model_name(model)
        output = episode_dir / f"transcript-{safe_model}.json"

        # Load audio metadata
        try:
            meta = AudioMeta.model_validate(selected["meta_data"])
        except Exception as e:
            raise ValidationError(f"Invalid AudioMeta input: {e}") from e

    else:
        # Non-interactive mode
        logger.info("Starting transcription", model=model, compute=compute)

        # Read input
        if input:
            raw_data = json.loads(input.read_text())
            logger.debug("Reading input from file", file=str(input))
        else:
            raw_data = read_stdin_json()
            logger.debug("Reading input from stdin")

        if not raw_data or "audio_path" not in raw_data:
            if json_output:
                print(
                    json.dumps(
                        {
                            "error": "input must contain AudioMeta JSON with 'audio_path' field",
                            "type": "validation_error",
                        }
                    )
                )
            else:
                from rich.console import Console
                console = Console()
                console.print(
                    "[red]Validation Error:[/red] input must contain AudioMeta JSON with 'audio_path' field"
                )
            sys.exit(ExitCode.USER_ERROR)

        # Validate input data
        try:
            meta = AudioMeta.model_validate(raw_data)
            audio = Path(meta.audio_path)
            logger.debug("Input validation passed", audio_path=str(audio))
        except Exception as e:
            if json_output:
                print(
                    json.dumps({"error": f"Invalid AudioMeta input: {e}", "type": "validation_error"})
                )
            else:
                from rich.console import Console
                console = Console()
                console.print(f"[red]Validation Error:[/red] Invalid AudioMeta input: {e}")
            sys.exit(ExitCode.USER_ERROR)

    # Determine provider
    provider_choice = None if asr_provider == "auto" else asr_provider

    # Parse additional decode options for expert mode
    extra_kwargs = {}
    if expert and decode_option:
        for opt in decode_option:
            if "=" in opt:
                k, v = opt.split("=", 1)
                extra_kwargs[k.strip()] = v.strip()

    # Determine VAD and conditioning settings
    use_vad = True if vad_filter is None else bool(vad_filter)
    use_condition = True if condition_on_previous_text is None else bool(condition_on_previous_text)

    # Set up progress callback for interactive mode or JSON progress
    timer = None
    progress_callback = None

    if progress_json and not interactive:
        # JSON progress mode
        def progress_callback(message: str):
            # Output newline-delimited JSON progress
            progress_data = {
                "type": "progress",
                "stage": "transcribing",
                "message": message,
            }
            print(json.dumps(progress_data), flush=True)
    elif interactive:
        # Suppress logging and show progress
        from podx.logging import suppress_logging

        suppress_logging()

        # Start live timer
        if RICH_AVAILABLE:
            console = Console()
            timer = LiveTimer("Transcribing")
            timer.start()

            def progress_callback(message: str):
                # Could update console here if needed
                pass

    # Use core transcription engine (pure business logic)
    try:
        # Pass None for compute_type if "auto" to enable auto-detection
        compute_type_arg = None if compute == "auto" else compute

        engine = TranscriptionEngine(
            model=model,
            provider=provider_choice,
            compute_type=compute_type_arg,
            device=None,  # Auto-detect best device (CUDA/CPU)
            vad_filter=use_vad,
            condition_on_previous_text=use_condition,
            extra_decode_options=extra_kwargs,
            progress_callback=progress_callback,
        )
        result = engine.transcribe(Path(audio))
    except TranscriptionError as e:
        if timer:
            timer.stop()
        if json_output:
            print(json.dumps({"error": str(e), "type": "transcription_error"}))
        else:
            from rich.console import Console
            console = Console()
            console.print(f"[red]Transcription Error:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)
    except AudioError as e:
        if timer:
            timer.stop()
        if json_output:
            print(json.dumps({"error": str(e), "type": "audio_error"}))
        else:
            from rich.console import Console
            console = Console()
            console.print(f"[red]Audio Error:[/red] {e}")
        sys.exit(ExitCode.USER_ERROR)

    # Stop timer and show completion in interactive mode
    if timer:
        elapsed = timer.stop()
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        console.print(f"[green]✓ Transcribe completed in {minutes}:{seconds:02d}[/green]")

    # Restore logging after transcription
    if interactive:
        from podx.logging import restore_logging

        restore_logging()

    # Handle output based on interactive mode
    if interactive:
        # In interactive mode, save to file
        output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        # Show user-friendly completion message
        print("\n✅ Transcription complete")
        print(f"   Model: {model} ({result['asr_provider']})")
        print(f"   Segments: {len(result['segments'])}")
        print(f"   Language: {result['language']}")
        print(f"   Output: {output}")
        logger.info(f"Transcript saved to: {output}")
    else:
        # Non-interactive mode: use model-specific filename if model specified and no explicit output
        transcript_path = None
        if model and not output:
            # Try to determine episode directory from audio path
            audio_dir = Path(audio).parent
            safe_model = sanitize_model_name(model)
            transcript_path = audio_dir / f"transcript-{safe_model}.json"
            transcript_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.debug("Transcript saved to file", file=str(transcript_path))
        elif output:
            # Explicit output file specified
            transcript_path = output
            transcript_path.write_text(json.dumps(result, indent=2))
            logger.debug("Transcript saved to file", file=str(transcript_path))

        # Output to stdout
        if json_output:
            # Structured JSON output
            output_data = {
                "success": True,
                "transcript": result,
                "files": {
                    "transcript": str(transcript_path) if transcript_path else None,
                },
                "stats": {
                    "model": model,
                    "provider": result.get("asr_provider"),
                    "language": result.get("language"),
                    "segments": len(result.get("segments", [])),
                },
            }
            print(json.dumps(output_data, indent=2))
        else:
            # Rich formatted output (existing behavior)
            print_json(result)

    # Exit with success
    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
