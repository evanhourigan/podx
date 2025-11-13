"""CLI wrapper for diarize command.

Thin Click wrapper that uses core.diarize.DiarizationEngine for actual logic.
Handles CLI arguments, input/output, and interactive mode with progress display.
"""

import json
import os
import sys
from pathlib import Path

import click

from podx.cli.cli_shared import print_json, read_stdin_json
from podx.core.diarize import DiarizationEngine, DiarizationError
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger
from podx.ui.diarize_browser import DiarizeTwoPhase
from podx.ui.live_timer import LiveTimer

logger = get_logger(__name__)

# Rich console for live timer
try:
    from rich.console import Console

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@click.command()
@click.option(
    "--audio",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Audio file path (optional if specified in transcript JSON)",
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read Transcript JSON from file instead of stdin",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save DiarizedTranscript JSON to file (also prints to stdout)",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive browser to select transcripts for diarization",
)
@click.option(
    "--scan-dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Directory to scan for transcripts (default: current directory)",
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
@click.option(
    "--keep-intermediates/--no-keep-intermediates",
    default=False,
    help="Keep intermediate files after diarization (default: auto-cleanup)",
)
def main(audio, input, output, interactive, scan_dir, json_output, progress_json, keep_intermediates):
    """
    Read transcript JSON -> WhisperX align + diarize -> print diarized JSON to stdout.

    Runs alignment internally before diarization. Alignment adds word-level timing,
    then diarization assigns speakers to each word.

    With --interactive, browse base transcripts and select one to diarize.
    """
    # Handle interactive mode
    if interactive:
        if not RICH_AVAILABLE:
            if json_output:
                print(
                    json.dumps(
                        {
                            "error": "Interactive mode requires rich library",
                            "install": "pip install rich",
                        }
                    )
                )
            else:
                console = Console()
                console.print(
                    "[red]Error:[/red] Interactive mode requires rich library. "
                    "Install with: [cyan]pip install rich[/cyan]"
                )
            sys.exit(ExitCode.USER_ERROR)

        # Two-phase selection: episode → base transcript
        logger.info(f"Scanning for episodes in: {scan_dir}")
        browser = DiarizeTwoPhase(scan_dir=Path(scan_dir))
        selected = browser.browse()

        if not selected:
            logger.info("User cancelled transcript selection")
            if not json_output:
                print("❌ Transcript selection cancelled")
            sys.exit(ExitCode.SUCCESS)

        # Use selected base transcript
        transcript = selected["transcript_data"]
        audio = selected["audio_path"]
        output = selected["diarized_file"]

    else:
        # Non-interactive mode
        # Read input
        if input:
            transcript = json.loads(input.read_text())
        else:
            transcript = read_stdin_json()

        if not transcript or "segments" not in transcript:
            if json_output:
                print(
                    json.dumps(
                        {
                            "error": "input must contain Transcript JSON with 'segments' field",
                            "type": "validation_error",
                        }
                    )
                )
            else:
                console = Console()
                console.print(
                    "[red]Validation Error:[/red] input must contain Transcript JSON with 'segments' field"
                )
            sys.exit(ExitCode.USER_ERROR)

    # Preserve metadata from input transcript
    asr_model = transcript.get("asr_model")
    language = transcript.get("language", "en")

    # Get audio path from --audio flag or from JSON (non-interactive mode)
    if not interactive and not audio:
        if "audio_path" not in transcript:
            if json_output:
                print(
                    json.dumps(
                        {
                            "error": "--audio flag required when transcript JSON has no 'audio_path' field",
                            "type": "validation_error",
                        }
                    )
                )
            else:
                console = Console()
                console.print(
                    "[red]Validation Error:[/red] --audio flag required when transcript JSON has no 'audio_path' field"
                )
            sys.exit(ExitCode.USER_ERROR)
        audio = Path(transcript["audio_path"])
        if not audio.exists():
            if json_output:
                print(
                    json.dumps(
                        {
                            "error": f"Audio file not found: {audio}",
                            "type": "file_not_found",
                        }
                    )
                )
            else:
                console = Console()
                console.print(f"[red]Error:[/red] Audio file not found: {audio}")
            sys.exit(ExitCode.USER_ERROR)

    # Ensure we use absolute path
    if not interactive:
        audio = audio.resolve()

    # Suppress logging and WhisperX output before TUI in interactive mode
    if interactive:
        from podx.logging import suppress_logging

        suppress_logging()

    # Set up progress callback and timer for interactive mode or JSON progress
    timer = None
    progress_callback = None
    console = None

    if progress_json and not interactive:
        # JSON progress mode
        def progress_callback(message: str):
            # Output newline-delimited JSON progress
            progress_data = {
                "type": "progress",
                "stage": "diarizing",
                "message": message,
            }
            print(json.dumps(progress_data), flush=True)

    elif interactive and RICH_AVAILABLE:
        console = Console()
        # Save original stdout before redirecting, so timer can still display
        original_stdout = sys.stdout
        timer = LiveTimer("Diarizing audio", output_stream=original_stdout)
        timer.start()

        def progress_callback(message: str):
            # Could update console here if needed
            pass

    # Suppress WhisperX debug output that contaminates stdout
    from contextlib import redirect_stderr, redirect_stdout

    # Use core diarization engine (pure business logic)
    try:
        with (
            redirect_stdout(open(os.devnull, "w")),
            redirect_stderr(open(os.devnull, "w")),
        ):
            engine = DiarizationEngine(
                language=language,
                device=None,  # Auto-detect best device (MPS/CUDA/CPU)
                hf_token=os.getenv("HUGGINGFACE_TOKEN"),
                progress_callback=progress_callback,
            )
            final = engine.diarize(audio, transcript["segments"])
    except DiarizationError as e:
        if timer:
            timer.stop()
        if json_output:
            print(json.dumps({"error": str(e), "type": "diarization_error"}))
        else:
            if not console:
                console = Console()
            console.print(f"[red]Diarization Error:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)
    except FileNotFoundError as e:
        if timer:
            timer.stop()
        if json_output:
            print(json.dumps({"error": str(e), "type": "file_not_found"}))
        else:
            if not console:
                console = Console()
            console.print(f"[red]File Not Found:[/red] {e}")
        sys.exit(ExitCode.USER_ERROR)

    # Stop timer and show completion in interactive mode
    if timer:
        elapsed = timer.stop()
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        console.print(
            f"[green]✓ Diarization completed in {minutes}:{seconds:02d}[/green]"
        )

    # Restore logging after diarization
    if interactive:
        from podx.logging import restore_logging

        restore_logging()

    # Preserve metadata from input transcript (always use absolute path)
    final["audio_path"] = str(
        audio if isinstance(audio, Path) else Path(audio).resolve()
    )
    final["language"] = language
    if asr_model:
        final["asr_model"] = asr_model

    # Handle output based on interactive mode
    if interactive:
        # In interactive mode, save to file (new format: transcript-diarized-{model}.json)
        output.write_text(
            json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Diarized transcript saved to: {output}")
        # Print completion message
        print("\n✅ Diarization complete")
        print(f"   Model: {asr_model}")
        print(f"   Output: {output}")
    else:
        # Non-interactive mode
        diarized_path = None
        if asr_model and not output:
            # Use model-specific filename in same directory as audio (new format)
            audio_dir = Path(audio).parent
            diarized_path = audio_dir / f"transcript-diarized-{asr_model}.json"
            diarized_path.write_text(
                json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        elif output:
            # Explicit output file specified
            diarized_path = output
            diarized_path.write_text(json.dumps(final, indent=2))

        # Output to stdout
        if json_output:
            # Count unique speakers
            speakers = set()
            for seg in final.get("segments", []):
                if seg.get("speaker"):
                    speakers.add(seg["speaker"])

            # Structured JSON output
            output_data = {
                "success": True,
                "transcript": final,
                "files": {
                    "transcript": str(diarized_path) if diarized_path else None,
                },
                "stats": {
                    "speakers_found": len(speakers),
                    "segments": len(final.get("segments", [])),
                    "language": final.get("language"),
                },
            }
            print(json.dumps(output_data, indent=2))
        else:
            # Rich formatted output (existing behavior)
            print_json(final)

    # Cleanup intermediate files if not keeping them
    # Note: Diarize processes transcript JSON and doesn't create intermediate files
    # Cleanup happens at the orchestrator level (podx run) for pipeline-wide intermediates
    if not keep_intermediates:
        # If input was from a file (not stdin), we could optionally clean it up
        # But we preserve input files by default - cleanup is for generated intermediates
        pass

    # Exit with success
    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
