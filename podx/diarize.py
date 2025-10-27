import json
import os
import sys
import threading
import time
from contextlib import redirect_stderr
from pathlib import Path

import click

from .cli_shared import print_json, read_stdin_json
from .logging import get_logger
from .ui.diarize_browser import DiarizeTwoPhase

logger = get_logger(__name__)

# Rich console for live timer
try:
    from rich.console import Console

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class LiveTimer:
    """Display a live timer that updates every second in the console."""

    def __init__(self, message: str = "Running", output_stream=None):
        self.message = message
        self.start_time = None
        self.stop_flag = threading.Event()
        self.thread = None
        # Save reference to output stream (defaults to sys.stdout)
        self.output_stream = output_stream or sys.stdout

    def _format_time(self, seconds: int) -> str:
        """Format seconds as M:SS."""
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"

    def _run(self):
        """Run the timer loop."""
        while not self.stop_flag.is_set():
            elapsed = int(time.time() - self.start_time)
            # Use \r to overwrite the line - write directly to saved output stream
            self.output_stream.write(f"\r{self.message} ({self._format_time(elapsed)})")
            self.output_stream.flush()
            time.sleep(1)

    def start(self):
        """Start the timer."""
        self.start_time = time.time()
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> float:
        """Stop the timer and return elapsed time."""
        elapsed = time.time() - self.start_time
        self.stop_flag.set()
        if self.thread:
            self.thread.join(timeout=2)
        # Clear the line
        self.output_stream.write("\r" + " " * 80 + "\r")
        self.output_stream.flush()
        return elapsed


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
    "input_file",
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
def main(audio, input_file, output, interactive, scan_dir):
    """
    Read transcript JSON -> WhisperX align + diarize -> print diarized JSON to stdout.

    Runs alignment internally before diarization. Alignment adds word-level timing,
    then diarization assigns speakers to each word.

    With --interactive, browse base transcripts and select one to diarize.
    """
    # Handle interactive mode
    if interactive:
        if not RICH_AVAILABLE:
            raise SystemExit(
                "Interactive mode requires rich library. Install with: pip install rich"
            )

        # Two-phase selection: episode → base transcript
        logger.info(f"Scanning for episodes in: {scan_dir}")
        browser = DiarizeTwoPhase(scan_dir=Path(scan_dir))
        selected = browser.browse()

        if not selected:
            logger.info("User cancelled transcript selection")
            print("❌ Transcript selection cancelled")
            sys.exit(0)

        # Use selected base transcript
        transcript = selected["transcript_data"]
        audio = selected["audio_path"]
        output = selected["diarized_file"]

    else:
        # Non-interactive mode
        # Read input
        if input_file:
            transcript = json.loads(input_file.read_text())
        else:
            transcript = read_stdin_json()

        if not transcript or "segments" not in transcript:
            raise SystemExit(
                "input must contain Transcript JSON with 'segments' field"
            )

    # Preserve metadata from input transcript
    asr_model = transcript.get("asr_model")
    language = transcript.get("language", "en")

    # Get audio path from --audio flag or from JSON (non-interactive mode)
    if not interactive and not audio:
        if "audio_path" not in transcript:
            raise SystemExit(
                "--audio flag required when transcript JSON has no 'audio_path' field"
            )
        audio = Path(transcript["audio_path"])
        if not audio.exists():
            raise SystemExit(f"Audio file not found: {audio}")

    # Ensure we use absolute path
    if not interactive:
        audio = audio.resolve()

    # Suppress WhisperX debug output that contaminates stdout
    from contextlib import redirect_stdout

    import whisperx
    from whisperx.diarize import DiarizationPipeline, assign_word_speakers

    # Suppress logging before TUI in interactive mode
    if interactive:
        from .logging import suppress_logging
        suppress_logging()

    # Save original stdout before redirecting, so timer can still display
    timer = None
    original_stdout = sys.stdout

    try:
        # Step 1: Alignment - add word-level timing using WhisperX
        if interactive and RICH_AVAILABLE:
            console = Console()
            timer = LiveTimer("Aligning transcript", output_stream=original_stdout)
            timer.start()

        with redirect_stdout(open(os.devnull, "w")), redirect_stderr(open(os.devnull, "w")):
            # Load alignment model
            model_a, metadata = whisperx.load_align_model(
                language_code=language, device="cpu"
            )

            # Load audio
            audio_data = whisperx.load_audio(str(audio))

            # Align segments
            aligned_result = whisperx.align(
                transcript["segments"],
                model_a,
                metadata,
                audio_data,
                device="cpu",
                return_char_alignments=False,
            )
            aligned = aligned_result  # Contains aligned segments with word-level timing

        # Show alignment completion
        if timer:
            elapsed = timer.stop()
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            console.print(f"[green]✓ Alignment completed in {minutes}:{seconds:02d}[/green]")

        # Step 2: Diarization - assign speakers to words
        if interactive and RICH_AVAILABLE:
            timer = LiveTimer("Diarizing (identifying speakers)", output_stream=original_stdout)
            timer.start()

        with redirect_stdout(open(os.devnull, "w")), redirect_stderr(open(os.devnull, "w")):
            dia = DiarizationPipeline(
                use_auth_token=os.getenv("HUGGINGFACE_TOKEN"), device="cpu"
            )
            diarized = dia(str(audio))
            final = assign_word_speakers(diarized, aligned)

        # Show diarization completion
        if timer:
            elapsed = timer.stop()
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            console.print(f"[green]✓ Diarization completed in {minutes}:{seconds:02d}[/green]")

    except Exception as e:
        if timer:
            timer.stop()
        raise SystemExit(f"Alignment + diarization failed: {e}") from e

    # Preserve metadata from input transcript (always use absolute path)
    final["audio_path"] = str(
        audio if isinstance(audio, Path) else Path(audio).resolve()
    )
    final["language"] = language
    if asr_model:
        final["asr_model"] = asr_model

    # Handle output based on interactive mode
    if interactive:
        # Restore logging
        from .logging import restore_logging
        restore_logging()

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
        if asr_model and not output:
            # Use model-specific filename in same directory as audio (new format)
            audio_dir = Path(audio).parent
            output = audio_dir / f"transcript-diarized-{asr_model}.json"
            output.write_text(
                json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        elif output:
            # Explicit output file specified
            output.write_text(json.dumps(final, indent=2))

        # Always print to stdout in non-interactive mode
        print_json(final)


if __name__ == "__main__":
    main()
