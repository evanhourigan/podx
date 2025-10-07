import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from .cli_shared import print_json, read_stdin_json
from .logging import get_logger
from .schemas import AudioMeta

logger = get_logger(__name__)

# Interactive browser imports (optional)
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def scan_episodes(base_dir: Path = Path.cwd()) -> List[Dict[str, Any]]:
    """Scan for episode-meta.json files in subdirectories."""
    episodes = []

    # Recursively search for episode-meta.json files
    for meta_file in base_dir.rglob("episode-meta.json"):
        try:
            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))

            # Check if audio file exists
            if "audio_path" not in meta_data:
                continue

            audio_path = Path(meta_data["audio_path"])
            if not audio_path.exists():
                # Try relative to meta file directory
                audio_path = meta_file.parent / audio_path.name
                if not audio_path.exists():
                    continue

            # Check for existing transcoded version
            audio_meta_path = meta_file.parent / "audio-meta.json"
            is_transcoded = audio_meta_path.exists()

            episodes.append(
                {
                    "meta_file": meta_file,
                    "meta_data": meta_data,
                    "audio_path": audio_path,
                    "is_transcoded": is_transcoded,
                    "directory": meta_file.parent,
                }
            )
        except Exception as e:
            logger.debug(f"Failed to parse {meta_file}: {e}")
            continue

    # Sort by directory path for consistent ordering
    episodes.sort(key=lambda x: str(x["directory"]))

    return episodes


def _truncate_text(text: str, max_length: int = 60) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


class TranscodeBrowser:
    """Interactive episode browser for transcoding."""

    def __init__(self, episodes: List[Dict[str, Any]], episodes_per_page: int = 10):
        self.episodes = episodes
        self.episodes_per_page = episodes_per_page
        self.console = Console() if RICH_AVAILABLE else None
        self.current_page = 0
        self.total_pages = (
            (len(episodes) + episodes_per_page - 1) // episodes_per_page
            if episodes
            else 1
        )

    def display_page(self) -> None:
        """Display current page of episodes."""
        if not self.console:
            return

        start_idx = self.current_page * self.episodes_per_page
        end_idx = min(start_idx + self.episodes_per_page, len(self.episodes))
        page_episodes = self.episodes[start_idx:end_idx]

        # Create title
        title = f"🎙️ Episodes Available for Transcoding (Page {self.current_page + 1}/{self.total_pages})"

        # Create table
        table = Table(show_header=True, header_style="bold magenta", title=title)
        table.add_column("#", style="cyan", width=3, justify="right")
        table.add_column("Status", style="yellow", width=8)
        table.add_column("Show", style="green", width=20)
        table.add_column("Date", style="blue", width=12)
        table.add_column("Title", style="white", width=50)

        # Add episodes to table
        for i, episode in enumerate(page_episodes):
            episode_num = start_idx + i + 1
            meta = episode["meta_data"]

            # Status indicator
            status = "✓ Done" if episode["is_transcoded"] else "○ New"

            # Extract info from metadata
            show = _truncate_text(meta.get("show", "Unknown"), 20)

            # Extract date from published or path
            date_str = meta.get("episode_published", "")
            if date_str:
                # Try to parse date
                try:
                    from dateutil import parser as dtparse

                    parsed = dtparse.parse(date_str)
                    date = parsed.strftime("%Y-%m-%d")
                except Exception:
                    date = date_str[:10] if len(date_str) >= 10 else date_str
            else:
                # Try to extract from directory name
                parts = str(episode["directory"]).split("/")
                date = parts[-1] if parts else "Unknown"

            title = _truncate_text(meta.get("episode_title", "Unknown"), 50)

            table.add_row(str(episode_num), status, show, date, title)

        self.console.print(table)

        # Show navigation options
        options = []
        options.append(
            f"[cyan]1-{len(self.episodes)}[/cyan]: Select episode to transcode"
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

        self.console.print(panel)

    def get_user_input(self) -> Optional[Dict[str, Any]]:
        """Get user input and return selected episode or None."""
        while True:
            try:
                user_input = input("\n👉 Your choice: ").strip().upper()

                if not user_input:
                    continue

                # Quit
                if user_input in ["Q", "QUIT", "EXIT"]:
                    if self.console:
                        self.console.print("👋 Goodbye!")
                    return None

                # Next page
                if user_input == "N" and self.current_page < self.total_pages - 1:
                    self.current_page += 1
                    return {}  # Empty dict signals page change

                # Previous page
                if user_input == "P" and self.current_page > 0:
                    self.current_page -= 1
                    return {}  # Empty dict signals page change

                # Episode selection
                try:
                    episode_num = int(user_input)
                    if 1 <= episode_num <= len(self.episodes):
                        selected_episode = self.episodes[episode_num - 1]
                        if self.console:
                            meta = selected_episode["meta_data"]
                            title = meta.get("episode_title", "Unknown")
                            status = (
                                "re-transcode"
                                if selected_episode["is_transcoded"]
                                else "transcode"
                            )
                            self.console.print(
                                f"✅ Selected episode {episode_num}: [green]{title}[/green] (will {status})"
                            )
                        return selected_episode
                    else:
                        if self.console:
                            self.console.print(
                                f"❌ Invalid episode number. Please choose 1-{len(self.episodes)}"
                            )
                except ValueError:
                    pass

                # Invalid input
                if self.console:
                    self.console.print("❌ Invalid input. Please try again.")

            except (KeyboardInterrupt, EOFError):
                if self.console:
                    self.console.print("\n👋 Goodbye!")
                return None

    def browse(self) -> Optional[Dict[str, Any]]:
        """Main browsing loop."""
        while True:
            if self.console:
                self.console.clear()
            self.display_page()

            result = self.get_user_input()

            # None means quit
            if result is None:
                return None

            # Empty dict means page change, continue loop
            if not result:
                continue

            # Non-empty dict means episode selected
            return result


def ffmpeg(args):
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error"] + args,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip())


def to_wav16(src: Path, dst: Path) -> Path:
    dst = dst.with_suffix(".wav")
    ffmpeg(["-y", "-i", str(src), "-ac", "1", "-ar", "16000", "-vn", str(dst)])
    return dst


def ffprobe_audio_meta(path: Path) -> Dict[str, Any]:
    """Probe audio stream for sample rate and channels using ffprobe (best effort)."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=sample_rate,channels",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return {}
        vals = [v for v in proc.stdout.strip().splitlines() if v]
        if len(vals) >= 2:
            return {"sample_rate": int(vals[0]), "channels": int(vals[1])}
    except Exception:
        pass
    return {}


@click.command()
@click.option(
    "--to",
    "fmt",
    default="wav16",
    type=click.Choice(["wav16", "mp3", "aac"]),
    show_default=True,
)
@click.option("--bitrate", default="128k", show_default=True)
@click.option(
    "--outdir",
    type=click.Path(path_type=Path),
    help="Output directory (defaults to same directory as source audio)",
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read EpisodeMeta JSON from file instead of stdin",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save AudioMeta JSON to file (also prints to stdout)",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive browser to select episodes for transcoding",
)
@click.option(
    "--scan-dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Directory to scan for episodes (default: current directory)",
)
def main(fmt, bitrate, outdir, input, output, interactive, scan_dir):
    """
    Read EpisodeMeta JSON on stdin (with audio_path), transcode, print AudioMeta JSON on stdout.

    With --interactive, browse episodes and select one to transcode.
    """
    # Handle interactive mode
    if interactive:
        if not RICH_AVAILABLE:
            raise SystemExit(
                "Interactive mode requires rich library. Install with: pip install rich"
            )

        # Scan for episodes
        logger.info(f"Scanning for episodes in: {scan_dir}")
        episodes = scan_episodes(Path(scan_dir))

        if not episodes:
            logger.error(f"No episodes found in {scan_dir}")
            raise SystemExit("No episodes with episode-meta.json found")

        logger.info(f"Found {len(episodes)} episodes")

        # Browse and select
        browser = TranscodeBrowser(episodes, episodes_per_page=10)
        selected = browser.browse()

        if not selected:
            logger.info("User cancelled")
            return

        # Use selected episode's metadata
        meta = selected["meta_data"]
        src = selected["audio_path"]
        episode_dir = selected["directory"]

        # Force outdir to episode directory in interactive mode
        outdir = episode_dir

        # Force output to audio-meta.json in interactive mode
        output = episode_dir / "audio-meta.json"

    else:
        # Non-interactive mode: read from input
        if input:
            meta = json.loads(input.read_text())
        else:
            meta = read_stdin_json()

        if not meta or "audio_path" not in meta:
            raise SystemExit(
                "input must contain EpisodeMeta JSON with 'audio_path' field"
            )
        src = Path(meta["audio_path"])

    # Determine output directory
    if outdir:
        # Use specified outdir
        output_dir = outdir
    else:
        # Default: use same directory as source audio
        output_dir = src.parent

    output_dir.mkdir(parents=True, exist_ok=True)
    dst = output_dir / src.stem

    if fmt == "wav16":
        wav = to_wav16(src, dst)
        out: AudioMeta = {
            "audio_path": str(wav),
            "sample_rate": 16000,
            "channels": 1,
            "format": "wav16",
        }
    elif fmt == "mp3":
        dst = dst.with_suffix(".mp3")
        ffmpeg(
            ["-y", "-i", str(src), "-codec:a", "libmp3lame", "-b:a", bitrate, str(dst)]
        )
        probed = ffprobe_audio_meta(dst)
        out = {"audio_path": str(dst), "format": "mp3", **probed}
    else:
        dst = dst.with_suffix(".m4a")
        ffmpeg(["-y", "-i", str(src), "-c:a", "aac", "-b:a", bitrate, str(dst)])
        probed = ffprobe_audio_meta(dst)
        out = {"audio_path": str(dst), "format": "aac", **probed}

    # Handle output based on interactive mode
    if interactive:
        # In interactive mode, save to file (already set to audio-meta.json)
        output.write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Audio metadata saved to: {output}")
    else:
        # Non-interactive mode: save to file if requested
        if output:
            output.write_text(json.dumps(out, indent=2))

        # Always print to stdout in non-interactive mode
        print_json(out)


if __name__ == "__main__":
    main()
