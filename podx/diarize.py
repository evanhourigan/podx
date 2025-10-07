import json
import os
import sys
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


def _truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def scan_diarizable_transcripts(scan_dir: Path) -> List[Dict[str, Any]]:
    """
    Scan directory for aligned-transcript-{model}.json files.
    Returns list of aligned transcripts with their metadata and diarization status.
    """
    transcripts = []

    # Find all aligned-transcript-{model}.json files
    for aligned_file in scan_dir.rglob("aligned-transcript-*.json"):
        try:
            # Load aligned transcript data
            aligned_data = json.loads(aligned_file.read_text(encoding="utf-8"))

            # Extract ASR model from filename
            filename = aligned_file.stem  # e.g., "aligned-transcript-large-v3"
            if filename.startswith("aligned-transcript-"):
                asr_model = filename[len("aligned-transcript-") :]
            else:
                continue

            # Get audio path
            audio_path = aligned_data.get("audio_path")
            if not audio_path:
                continue

            audio_path = Path(audio_path)
            if not audio_path.exists():
                continue

            # Check if diarized version exists
            diarized_file = (
                aligned_file.parent / f"diarized-transcript-{asr_model}.json"
            )
            is_diarized = diarized_file.exists()

            # Try to get episode metadata for better display
            episode_meta_file = aligned_file.parent / "episode-meta.json"
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
                    "aligned_file": aligned_file,
                    "aligned_data": aligned_data,
                    "audio_path": audio_path,
                    "asr_model": asr_model,
                    "is_diarized": is_diarized,
                    "diarized_file": diarized_file,
                    "episode_meta": episode_meta,
                    "directory": aligned_file.parent,
                }
            )
        except Exception as e:
            logger.debug(f"Failed to parse {aligned_file}: {e}")
            continue

    # Sort by date (most recent first) then by show name
    def sort_key(t):
        date_str = t["episode_meta"].get("episode_published", "")
        return (date_str, t["episode_meta"].get("show", ""))

    transcripts.sort(key=sort_key, reverse=True)
    return transcripts


class DiarizeBrowser:
    """Interactive browser for selecting aligned transcripts to diarize."""

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

            # Create header
            title = f"Episodes Available for Transcription Diarization (Page {self.current_page + 1}/{self.total_pages})"
            console.print(Panel(title, style="bold cyan"))
            console.print()

            # Create table
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("#", style="cyan", width=6, justify="right")
            table.add_column("Status", style="yellow", width=15)
            table.add_column("Show", style="green", width=25)
            table.add_column("Date", style="blue", width=12)
            table.add_column("Title", style="white")

            for idx, item in enumerate(page_items, start=start_idx + 1):
                episode_meta = item["episode_meta"]
                asr_model = item["asr_model"]
                status = f"✓ {asr_model}" if item["is_diarized"] else f"○ {asr_model}"

                show = _truncate_text(episode_meta.get("show", "Unknown"), 25)
                date = episode_meta.get("episode_published", "")[:10]
                title = _truncate_text(episode_meta.get("episode_title", "Unknown"), 40)

                table.add_row(str(idx), status, show, date, title)

            console.print(table)
            console.print()

            # Show options
            options = (
                f"[cyan]1-{len(self.transcripts)}:[/cyan] Select episode to diarize"
            )
            if self.total_pages > 1:
                options += " • [cyan]N:[/cyan] Next page"
            options += " • [cyan]Q:[/cyan] Quit"
            console.print(options)
            console.print()

            # Get user input
            choice = input("👉 Your choice: ").strip().upper()

            if choice in ["Q", "QUIT"]:
                return None
            elif choice == "N" and self.total_pages > 1:
                self.current_page = (self.current_page + 1) % self.total_pages
            else:
                try:
                    selection = int(choice)
                    if 1 <= selection <= len(self.transcripts):
                        return self.transcripts[selection - 1]
                    else:
                        console.print(
                            f"[red]❌ Invalid choice. Please select 1-{len(self.transcripts)}[/red]"
                        )
                        input("Press Enter to continue...")
                except ValueError:
                    console.print("[red]❌ Invalid input. Please enter a number.[/red]")
                    input("Press Enter to continue...")


@click.command()
@click.option(
    "--audio",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Audio file path (optional if specified in aligned transcript JSON)",
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read AlignedTranscript JSON from file instead of stdin",
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
    help="Interactive browser to select aligned transcripts for diarization",
)
@click.option(
    "--scan-dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Directory to scan for aligned transcripts (default: current directory)",
)
def main(audio, input, output, interactive, scan_dir):
    """
    Read aligned JSON on stdin -> WhisperX diarization -> print diarized JSON to stdout.

    With --interactive, browse aligned transcripts and select one to diarize.
    """
    # Handle interactive mode
    if interactive:
        if not RICH_AVAILABLE:
            raise SystemExit(
                "Interactive mode requires rich library. Install with: pip install rich"
            )

        console = Console()

        # Scan for aligned transcripts
        logger.info(f"Scanning for aligned transcripts in: {scan_dir}")
        transcripts = scan_diarizable_transcripts(Path(scan_dir))

        if not transcripts:
            logger.error(f"No aligned transcripts found in {scan_dir}")
            raise SystemExit("No aligned-transcript-*.json files found")

        logger.info(f"Found {len(transcripts)} aligned transcripts")

        # Browse and select transcript
        browser = DiarizeBrowser(transcripts, items_per_page=10)
        selected = browser.browse()

        if not selected:
            logger.info("User cancelled transcript selection")
            sys.exit(0)

        # Check if already diarized - confirm if so
        if selected["is_diarized"]:
            console.print(
                f"\n[yellow]⚠ This transcript is already diarized (model: {selected['asr_model']})[/yellow]"
            )
            confirm = input("Re-diarize anyway? (yes/no): ").strip().lower()
            if confirm not in ["yes", "y"]:
                console.print("[dim]Diarization cancelled.[/dim]")
                sys.exit(0)

        # Use selected aligned transcript
        aligned = selected["aligned_data"]
        audio = selected["audio_path"]
        output = selected["diarized_file"]

    else:
        # Non-interactive mode
        # Read input
        if input:
            aligned = json.loads(input.read_text())
        else:
            aligned = read_stdin_json()

        if not aligned or "segments" not in aligned:
            raise SystemExit(
                "input must contain AlignedTranscript JSON with 'segments' field"
            )

    # Preserve metadata from input aligned transcript
    asr_model = aligned.get("asr_model")
    language = aligned.get("language", "en")

    # Get audio path from --audio flag or from JSON (non-interactive mode)
    if not interactive and not audio:
        if "audio_path" not in aligned:
            raise SystemExit(
                "--audio flag required when aligned transcript JSON has no 'audio_path' field"
            )
        audio = Path(aligned["audio_path"])
        if not audio.exists():
            raise SystemExit(f"Audio file not found: {audio}")

    # Ensure we use absolute path
    if not interactive:
        audio = audio.resolve()

    # Suppress WhisperX debug output that contaminates stdout
    import sys
    from contextlib import redirect_stderr, redirect_stdout

    from whisperx import diarize

    with redirect_stdout(open(os.devnull, "w")), redirect_stderr(open(os.devnull, "w")):
        dia = diarize.DiarizationPipeline(
            use_auth_token=os.getenv("HUGGINGFACE_TOKEN"), device="cpu"
        )
        diarized = dia(str(audio))
        final = diarize.assign_word_speakers(diarized, aligned)

    # Preserve metadata from input transcript (always use absolute path)
    final["audio_path"] = str(
        audio if isinstance(audio, Path) else Path(audio).resolve()
    )
    final["language"] = language
    if asr_model:
        final["asr_model"] = asr_model

    # Handle output based on interactive mode
    if interactive:
        # In interactive mode, save to file (already set to diarized-transcript-{model}.json)
        output.write_text(
            json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Diarized transcript saved to: {output}")
    else:
        # Non-interactive mode
        if asr_model and not output:
            # Use model-specific filename in same directory as audio
            audio_dir = Path(audio).parent
            output = audio_dir / f"diarized-transcript-{asr_model}.json"
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
