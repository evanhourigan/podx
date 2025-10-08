import json
import os
import sys
import threading
import time
from contextlib import redirect_stderr
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from .cli_shared import print_json, read_stdin_json
from .logging import get_logger

logger = get_logger(__name__)

# Interactive browser imports (optional)
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

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


def _truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def scan_alignable_transcripts(scan_dir: Path) -> List[Dict[str, Any]]:
    """
    Scan directory for transcript-{model}.json files.
    Returns list of transcripts with their metadata and alignment status.
    """
    transcripts = []

    # Find all transcript-{model}.json files
    for transcript_file in scan_dir.rglob("transcript-*.json"):
        try:
            # Load transcript data
            transcript_data = json.loads(transcript_file.read_text(encoding="utf-8"))

            # Extract ASR model from filename
            filename = transcript_file.stem  # e.g., "transcript-large-v3"
            if filename.startswith("transcript-"):
                asr_model = filename[len("transcript-") :]
            else:
                continue

            # Get audio path
            audio_path = transcript_data.get("audio_path")
            if not audio_path:
                continue

            audio_path = Path(audio_path)
            if not audio_path.exists():
                continue

            # Check if aligned version exists (new format first, then legacy)
            aligned_file_new = (
                transcript_file.parent / f"transcript-aligned-{asr_model}.json"
            )
            aligned_file_legacy = (
                transcript_file.parent / f"aligned-transcript-{asr_model}.json"
            )
            is_aligned = aligned_file_new.exists() or aligned_file_legacy.exists()
            # Use new format for output
            aligned_file = aligned_file_new

            # Try to get episode metadata for better display
            episode_meta_file = transcript_file.parent / "episode-meta.json"
            episode_meta = {}
            if episode_meta_file.exists():
                try:
                    episode_meta = json.loads(
                        episode_meta_file.read_text(encoding="utf-8")
                    )
                except Exception:
                    episode_meta = {}

            transcripts.append(
                {
                    "transcript_file": transcript_file,
                    "transcript_data": transcript_data,
                    "audio_path": audio_path,
                    "asr_model": asr_model,
                    "is_aligned": is_aligned,
                    "aligned_file": aligned_file,
                    "episode_meta": episode_meta,
                    "directory": transcript_file.parent,
                }
            )
        except Exception as e:
            logger.debug(f"Failed to parse {transcript_file}: {e}")
            continue

    # Sort by date (most recent first) then by show name
    def sort_key(t):
        date_str = t["episode_meta"].get("episode_published", "")
        return (date_str, t["episode_meta"].get("show", ""))

    transcripts.sort(key=sort_key, reverse=True)
    return transcripts


class AlignBrowser:
    """Interactive browser for selecting transcripts to align."""

    def __init__(self, transcripts: List[Dict[str, Any]], items_per_page: int = 10):
        self.transcripts = transcripts
        self.items_per_page = items_per_page
        self.current_page = 0
        self.total_pages = max(
            1, (len(transcripts) + items_per_page - 1) // items_per_page
        )

    def browse(self) -> Optional[Dict[str, Any]]:
        """Display interactive browser and return selected transcript."""
        if not RICH_AVAILABLE:
            return None

        console = Console()

        while True:
            console.clear()

            # Calculate page bounds
            start_idx = self.current_page * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.transcripts))
            page_items = self.transcripts[start_idx:end_idx]

            # Create title with emoji
            title = f"🎙️ Episodes Available for Transcription Alignment (Page {self.current_page + 1}/{self.total_pages})"

            # Create table
            table = Table(show_header=True, header_style="bold magenta", title=title)
            table.add_column("#", style="cyan", width=3, justify="right")
            table.add_column("Status", style="yellow", width=25)
            table.add_column("Show", style="green", width=18)
            table.add_column("Date", style="blue", width=12)
            table.add_column("Title", style="white", width=45)

            for idx, item in enumerate(page_items, start=start_idx + 1):
                episode_meta = item["episode_meta"]
                asr_model = item["asr_model"]
                status = f"✓ {asr_model}" if item["is_aligned"] else f"○ {asr_model}"

                show = _truncate_text(episode_meta.get("show", "Unknown"), 18)

                # Format date like transcribe does
                date_str = episode_meta.get("episode_published", "")
                if date_str:
                    try:
                        from dateutil import parser as dtparse

                        parsed = dtparse.parse(date_str)
                        date = parsed.strftime("%Y-%m-%d")
                    except Exception:
                        date = date_str[:10] if len(date_str) >= 10 else date_str
                else:
                    # Try to extract from directory name
                    parts = str(item["directory"]).split("/")
                    date = parts[-1] if parts else "Unknown"

                title_text = _truncate_text(
                    episode_meta.get("episode_title", "Unknown"), 45
                )

                table.add_row(str(idx), status, show, date, title_text)

            console.print(table)

            # Show navigation options in Panel
            options = []
            options.append(
                f"[cyan]1-{len(self.transcripts)}[/cyan]: Select episode to align"
            )

            if self.current_page < self.total_pages - 1:
                options.append("[yellow]N[/yellow]: Next page")

            if self.current_page > 0:
                options.append("[yellow]P[/yellow]: Previous page")

            options.append("[red]Q[/red]: Quit")

            options_text = " • ".join(options)
            panel = Panel(
                options_text, title="Options", border_style="blue", padding=(0, 1)
            )
            console.print(panel)

            # Get user input
            choice = input("\n👉 Your choice: ").strip().upper()

            if choice in ["Q", "QUIT", "EXIT"]:
                console.print("👋 Goodbye!")
                return None
            elif choice == "N" and self.current_page < self.total_pages - 1:
                self.current_page += 1
            elif choice == "P" and self.current_page > 0:
                self.current_page -= 1
            else:
                try:
                    selection = int(choice)
                    if 1 <= selection <= len(self.transcripts):
                        return self.transcripts[selection - 1]
                    else:
                        console.print(
                            f"❌ Invalid episode number. Please choose 1-{len(self.transcripts)}"
                        )
                except ValueError:
                    console.print("❌ Invalid input. Please try again.")


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
    help="Save AlignedTranscript JSON to file (also prints to stdout)",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive browser to select transcripts for alignment",
)
@click.option(
    "--scan-dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Directory to scan for transcripts (default: current directory)",
)
def main(audio, input, output, interactive, scan_dir):
    """
    Read coarse Transcript JSON on stdin -> WhisperX align -> print aligned JSON to stdout.

    With --interactive, browse transcripts and select one to align.
    """
    # Handle interactive mode
    if interactive:
        if not RICH_AVAILABLE:
            raise SystemExit(
                "Interactive mode requires rich library. Install with: pip install rich"
            )

        console = Console()

        # Scan for transcripts
        logger.info(f"Scanning for transcripts in: {scan_dir}")
        transcripts = scan_alignable_transcripts(Path(scan_dir))

        if not transcripts:
            logger.error(f"No transcripts found in {scan_dir}")
            raise SystemExit("No transcript-*.json files found")

        logger.info(f"Found {len(transcripts)} transcripts")

        # Browse and select transcript
        browser = AlignBrowser(transcripts, items_per_page=10)
        selected = browser.browse()

        if not selected:
            logger.info("User cancelled transcript selection")
            sys.exit(0)

        # Check if already aligned - confirm if so
        if selected["is_aligned"]:
            console.print(
                f"\n[yellow]⚠ This transcript is already aligned (model: {selected['asr_model']})[/yellow]"
            )
            confirm = input("Re-align anyway? (yes/no): ").strip().lower()
            if confirm not in ["yes", "y"]:
                console.print("[dim]Alignment cancelled.[/dim]")
                sys.exit(0)

        # Use selected transcript
        base = selected["transcript_data"]
        audio = selected["audio_path"]
        output = selected["aligned_file"]

    else:
        # Non-interactive mode
        # Read input
        if input:
            base = json.loads(input.read_text())
        else:
            base = read_stdin_json()

        if not base or "segments" not in base:
            raise SystemExit("input must contain Transcript JSON with 'segments' field")

    lang = base.get("language", "en")
    segs = base["segments"]

    # Preserve ASR model from input for filename
    asr_model = base.get("asr_model")

    # Get audio path from --audio flag or from JSON (non-interactive mode)
    if not interactive and not audio:
        if "audio_path" not in base:
            raise SystemExit(
                "--audio flag required when transcript JSON has no 'audio_path' field"
            )
        audio = Path(base["audio_path"])
        if not audio.exists():
            raise SystemExit(f"Audio file not found: {audio}")

    # Ensure we use absolute path
    if not interactive:
        audio = audio.resolve()

    # Suppress WhisperX debug output that contaminates stdout
    from contextlib import redirect_stderr, redirect_stdout

    import whisperx

    # Start live timer in interactive mode
    # Save original stdout before redirecting, so timer can still display
    timer = None
    original_stdout = sys.stdout
    if interactive and RICH_AVAILABLE:
        console = Console()
        timer = LiveTimer("Aligning", output_stream=original_stdout)
        timer.start()

    try:
        with redirect_stdout(open(os.devnull, "w")), redirect_stderr(open(os.devnull, "w")):
            model_a, metadata = whisperx.load_align_model(language_code=lang, device="cpu")
            aligned = whisperx.align(segs, model_a, metadata, str(audio), device="cpu")
    except Exception as e:
        if timer:
            timer.stop()
        raise SystemExit(f"Alignment failed: {e}") from e

    # Stop timer and show completion message in interactive mode
    if timer:
        elapsed = timer.stop()
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        console.print(f"[green]✓ Align completed in {minutes}:{seconds:02d}[/green]")

    # Preserve metadata from input transcript (always use absolute path)
    aligned["audio_path"] = str(
        audio if isinstance(audio, Path) else Path(audio).resolve()
    )
    aligned["language"] = lang
    if asr_model:
        aligned["asr_model"] = asr_model

    # Handle output based on interactive mode
    if interactive:
        # In interactive mode, save to file (new format: transcript-aligned-{model}.json)
        output.write_text(
            json.dumps(aligned, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Aligned transcript saved to: {output}")
    else:
        # Non-interactive mode
        if asr_model and not output:
            # Use model-specific filename in same directory as audio (new format)
            audio_dir = Path(audio).parent
            output = audio_dir / f"transcript-aligned-{asr_model}.json"
            output.write_text(
                json.dumps(aligned, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        elif output:
            # Explicit output file specified
            output.write_text(json.dumps(aligned, indent=2))

        # Always print to stdout in non-interactive mode
        print_json(aligned)


if __name__ == "__main__":
    main()
