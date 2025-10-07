import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse

import click
import feedparser
import requests
from dateutil import parser as dtparse

from .cli_shared import print_json, read_stdin_json
from .config import get_config
from .errors import NetworkError, ValidationError, with_retries
from .logging import get_logger
from .schemas import EpisodeMeta
from .validation import validate_output

logger = get_logger(__name__)

UA = "podx/1.0 (+mac cli)"

# Interactive browser imports (optional)
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def _sanitize(s: str) -> str:
    # Keep spaces, only replace truly problematic characters
    return re.sub(r'[<>:"/\\|?*]', "_", s.strip())


def _generate_workdir(show_name: str, episode_date: str) -> Path:
    """Generate a work directory path based on show name and episode date."""
    # Sanitize show name for filesystem
    safe_show = _sanitize(show_name)

    # Parse and format date
    try:
        parsed_date = dtparse.parse(episode_date)
        date_str = parsed_date.strftime("%Y-%m-%d")
    except Exception:
        # Fallback to original date string if parsing fails
        date_str = _sanitize(episode_date)

    return Path(safe_show) / date_str


# Interactive browser helper functions
def _format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds to HH:MM:SS format."""
    if not seconds:
        return "Unknown"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_date(date_str: str) -> str:
    """Format date string to readable format."""
    try:
        # Parse various date formats
        for fmt in [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
        ]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Fallback: just return first 10 chars if it looks like a date
        if len(date_str) >= 10:
            return date_str[:10]
        return date_str
    except Exception:
        return date_str


def _truncate_text(text: str, max_length: int = 80) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


class EpisodeBrowser:
    """Interactive episode browser with pagination."""

    def __init__(
        self, show_name: str, rss_url: Optional[str] = None, episodes_per_page: int = 8
    ):
        self.show_name = show_name
        self.rss_url = rss_url
        self.episodes_per_page = episodes_per_page
        self.console = Console() if RICH_AVAILABLE else None
        self.episodes: List[Dict[str, Any]] = []
        self.current_page = 0
        self.total_pages = 0

    def load_episodes(self) -> bool:
        """Load episodes from RSS feed."""
        try:
            # Find RSS feed if not provided
            if not self.rss_url:
                if self.console:
                    self.console.print(
                        f"🔍 Finding RSS feed for: [cyan]{self.show_name}[/cyan]"
                    )
                feed_url = find_feed_for_show(self.show_name)
                if not feed_url:
                    if self.console:
                        self.console.print(
                            f"❌ Could not find RSS feed for: {self.show_name}"
                        )
                    return False
                self.rss_url = feed_url

            # Parse RSS feed
            if self.console:
                self.console.print(
                    f"📡 Loading episodes from: [yellow]{self.rss_url}[/yellow]"
                )
            feed = feedparser.parse(self.rss_url)

            if not feed.entries:
                if self.console:
                    self.console.print("❌ No episodes found in RSS feed")
                return False

            # Extract episode information
            self.episodes = []
            for entry in feed.entries:
                # Get audio URL from enclosures
                audio_url = None
                duration = None

                # Extract duration from iTunes tags first (more reliable)
                if hasattr(entry, "itunes_duration"):
                    try:
                        duration_str = entry.itunes_duration
                        # Check if it's already in seconds (pure number)
                        try:
                            duration = int(duration_str)
                        except ValueError:
                            # Parse HH:MM:SS or MM:SS format
                            parts = duration_str.split(":")
                            if len(parts) == 3:  # HH:MM:SS
                                duration = (
                                    int(parts[0]) * 3600
                                    + int(parts[1]) * 60
                                    + int(parts[2])
                                )
                            elif len(parts) == 2:  # MM:SS
                                duration = int(parts[0]) * 60 + int(parts[1])
                    except (ValueError, AttributeError):
                        pass

                if hasattr(entry, "enclosures") and entry.enclosures:
                    for enclosure in entry.enclosures:
                        if enclosure.type and "audio" in enclosure.type:
                            audio_url = enclosure.href
                            break

                episode = {
                    "title": entry.title,
                    "published": (
                        entry.published if hasattr(entry, "published") else "Unknown"
                    ),
                    "description": entry.summary if hasattr(entry, "summary") else "",
                    "audio_url": audio_url,
                    "duration": duration,
                    "link": entry.link if hasattr(entry, "link") else "",
                }

                self.episodes.append(episode)

            # Calculate pagination
            self.total_pages = (
                len(self.episodes) + self.episodes_per_page - 1
            ) // self.episodes_per_page

            if self.console:
                self.console.print(
                    f"✅ Loaded [green]{len(self.episodes)}[/green] episodes"
                )
            return True

        except Exception as e:
            if self.console:
                self.console.print(f"❌ Error loading episodes: {e}")
            return False

    def display_page(self) -> None:
        """Display current page of episodes."""
        if not self.console:
            return

        start_idx = self.current_page * self.episodes_per_page
        end_idx = min(start_idx + self.episodes_per_page, len(self.episodes))
        page_episodes = self.episodes[start_idx:end_idx]

        # Create title
        title = f"🎙️ {self.show_name} - Episodes (Page {self.current_page + 1}/{self.total_pages})"

        # Create table
        table = Table(show_header=True, header_style="bold magenta", title=title)
        table.add_column("#", style="cyan", width=3, justify="right")
        table.add_column("Date", style="green", width=12)
        table.add_column("Duration", style="yellow", width=8, justify="right")
        table.add_column("Title", style="white")

        # Add episodes to table
        for i, episode in enumerate(page_episodes):
            episode_num = start_idx + i + 1
            date = _format_date(episode["published"])
            duration = _format_duration(episode["duration"])
            title_text = _truncate_text(episode["title"], 60)

            table.add_row(str(episode_num), date, duration, title_text)

        self.console.print(table)

        # Show navigation options
        options = []
        options.append(
            "[cyan]1-{max_num}[/cyan]: Select episode".format(
                max_num=len(self.episodes)
            )
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
                            self.console.print(
                                f"✅ Selected episode {episode_num}: [green]{selected_episode['title']}[/green]"
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
        if not self.load_episodes():
            return None

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


@with_retries(retry_on=(requests.exceptions.RequestException, NetworkError))
def find_feed_for_show(show_name: str) -> str:
    """Find RSS feed URL for a podcast show using iTunes API."""
    q = {"media": "podcast", "term": show_name}
    url = "https://itunes.apple.com/search?" + urlencode(q)

    logger.debug("Searching for podcast", show_name=show_name, url=url)

    # Try with different session configuration to avoid connection issues
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    try:
        r = session.get(url, timeout=30, verify=True)
        r.raise_for_status()
        data = r.json()
        logger.debug(
            "iTunes API response received", results_count=len(data.get("results", []))
        )
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
        logger.debug("Primary request failed, trying curl fallback", error=str(e))
        # Fallback: use curl via subprocess
        import json
        import subprocess

        try:
            result = subprocess.run(
                ["curl", "-s", url], capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                raise NetworkError(f"curl failed with return code {result.returncode}")
            data = json.loads(result.stdout)
            logger.debug(
                "iTunes search via curl successful",
                results_count=len(data.get("results", [])),
            )
        except Exception as curl_e:
            raise NetworkError(
                f"Failed to connect to iTunes API: {e}. Also tried curl: {curl_e}"
            ) from curl_e

    results = data.get("results") or []
    if not results:
        raise ValidationError(f"No podcasts found for: {show_name}")

    feed_url = results[0].get("feedUrl")
    if not feed_url:
        raise ValidationError("Found podcast but no feedUrl.")

    logger.info("Found podcast feed", show_name=show_name, feed_url=feed_url)
    return feed_url


def choose_episode(entries, date_str: Optional[str], title_contains: Optional[str]):
    """Choose the best matching episode from feed entries."""
    logger.debug(
        "Choosing episode",
        total_entries=len(entries),
        date_filter=date_str,
        title_filter=title_contains,
    )

    if title_contains:
        for e in entries:
            if title_contains.lower() in (e.get("title", "").lower()):
                logger.info(
                    "Found episode by title",
                    title=e.get("title", ""),
                    filter=title_contains,
                )
                return e

    if date_str:
        want = dtparse.parse(date_str)
        # Normalize to naive datetime for comparison
        if want.tzinfo is not None:
            want = want.replace(tzinfo=None)

        best = None
        best_delta = None
        for e in entries:
            d = e.get("published") or e.get("updated")
            if not d:
                continue
            try:
                dt = dtparse.parse(d)
                # Normalize to naive datetime for comparison
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
            except Exception:
                continue
            delta = abs((dt - want).total_seconds())
            if best is None or delta < best_delta:
                best, best_delta = e, delta

        if best:
            logger.info(
                "Found episode by date",
                title=best.get("title", ""),
                published=best.get("published", ""),
                delta_seconds=best_delta,
            )
            return best

    # Default to first episode
    if entries:
        logger.info("Using most recent episode", title=entries[0].get("title", ""))
        return entries[0]

    return None


def download_enclosure(entry, out_dir: Path) -> Path:
    """Download audio file from episode entry."""
    links = entry.get("links", []) or []
    audio = None
    for ln in links:
        if ln.get("rel") == "enclosure" and "audio" in (ln.get("type") or ""):
            audio = ln.get("href")
            break
    audio = audio or entry.get("link")

    if not audio:
        raise ValidationError("No audio enclosure found.")

    logger.debug("Downloading audio", url=audio, output_dir=str(out_dir))

    out_dir.mkdir(parents=True, exist_ok=True)

    # Extract clean file extension from URL (strip query parameters)
    parsed_url = urlparse(audio)
    clean_path = parsed_url.path
    extension = Path(clean_path).suffix or ".mp3"  # Default to .mp3 if no extension

    name = _sanitize(entry.get("title", "episode")) + extension
    dest = out_dir / name

    # Simple retries with backoff
    backoffs = [0, 1, 2, 4]
    last_err: Exception | None = None
    for attempt, delay in enumerate(backoffs):
        try:
            if delay:
                logger.debug("Retrying download", attempt=attempt + 1, delay=delay)
                from time import sleep

                sleep(delay)
            with requests.get(
                audio, stream=True, headers={"User-Agent": UA}, timeout=60
            ) as r:
                r.raise_for_status()
                total_size = int(r.headers.get("content-length", 0))

                with open(dest, "wb") as f:
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

            logger.info(
                "Audio downloaded",
                file=str(dest),
                size_mb=round(downloaded / (1024 * 1024), 2),
            )
            last_err = None
            break
        except Exception as e:
            last_err = e
            logger.warning("Download attempt failed", attempt=attempt + 1, error=str(e))
            continue

    if last_err is not None and not dest.exists():
        raise NetworkError(f"Failed to download enclosure: {last_err}")
    return dest


@click.command()
@click.option("--show", help="Podcast show name (iTunes search).")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show).")
@click.option("--date", help="Episode date (YYYY-MM-DD). Picks nearest.")
@click.option("--title-contains", help="Substring to match in episode title.")
@click.option(
    "--outdir",
    type=click.Path(path_type=Path),
    help="Override output directory (bypasses smart naming)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save EpisodeMeta JSON to file (also prints to stdout)",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive episode browser (ignores --date and --title-contains)",
)
@validate_output(EpisodeMeta)
def main(show, rss_url, date, title_contains, outdir, output, interactive):
    """Find feed, choose episode, download audio. Prints EpisodeMeta JSON to stdout."""
    logger.info(
        "Starting podcast fetch",
        show=show,
        rss_url=rss_url,
        date=date,
        title_contains=title_contains,
        interactive=interactive,
    )

    # Validate that either show or rss_url is provided
    if not show and not rss_url:
        raise ValidationError("Either --show or --rss-url must be provided.")
    if show and rss_url:
        raise ValidationError("Provide either --show or --rss-url, not both.")

    # Handle interactive mode
    if interactive:
        # Check if rich is available
        if not RICH_AVAILABLE:
            raise ValidationError(
                "Interactive mode requires additional dependencies (rich). "
                "Install with: pip install rich"
            )

        # Create and run browser
        browser = EpisodeBrowser(
            show_name=show or "Podcast", rss_url=rss_url, episodes_per_page=8
        )

        selected_episode = browser.browse()

        if not selected_episode:
            logger.info("User cancelled episode selection")
            sys.exit(0)

        # Extract episode details from selection
        # Convert browser episode format to fetch parameters
        episode_date = selected_episode.get("published", "")
        episode_title = selected_episode.get("title", "")

        # Override parameters with selection
        date = episode_date
        title_contains = None  # Use date matching instead

        # Get the actual feed URL from browser
        if browser.rss_url:
            rss_url = browser.rss_url
            feed_url = rss_url
            show_name = show or "Podcast"

        logger.info(
            "Episode selected interactively",
            title=episode_title,
            date=episode_date,
        )

        # Continue with normal fetch logic using the selected episode's date

    # Get feed URL (skip if already set by interactive mode)
    if interactive and "feed_url" in locals():
        # Already set by interactive mode
        pass
    elif rss_url:
        feed_url = rss_url
        show_name = None  # Will be extracted from feed
        logger.debug("Using direct RSS URL", url=rss_url)
    else:
        feed_url = find_feed_for_show(show)
        show_name = show

    # Parse feed
    logger.debug("Parsing RSS feed", url=feed_url)
    f = feedparser.parse(feed_url)
    if f.bozo:
        raise ValidationError(f"Failed to parse feed: {feed_url}")

    # Extract show name from feed if not provided or not set by interactive mode
    if "show_name" not in locals() or not show_name:
        show_name = f.feed.get("title", "Unknown Show")
        logger.debug("Extracted show name from feed", show_name=show_name)

    # Choose episode
    ep = choose_episode(f.entries, date, title_contains)
    if not ep:
        raise ValidationError("No episode found.")

    # Determine output directory
    if outdir:
        # Override: use specified outdir
        workdir = outdir
    else:
        # Default: use smart naming with spaces
        episode_date = ep.get("published") or ep.get("updated") or date or "unknown"
        workdir = _generate_workdir(show_name, episode_date)

    # Download audio
    audio_path = download_enclosure(ep, workdir)

    # Build metadata
    meta: EpisodeMeta = {
        "show": show_name,
        "feed": feed_url,
        "episode_title": ep.get("title", ""),
        "episode_published": (ep.get("published") or ep.get("updated") or ""),
        "audio_path": str(audio_path),
    }

    # Add image URL if available from feed
    if f.feed.get("image", {}).get("href"):
        meta["image_url"] = f.feed["image"]["href"]

    # Handle output based on interactive mode
    if interactive:
        # In interactive mode, save to episode directory
        if not output:
            output = workdir / "episode-meta.json"
        output.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Episode metadata saved", file=str(output))
    else:
        # Non-interactive mode: save to file if requested
        if output:
            output.write_text(json.dumps(meta, indent=2))

        # Always print to stdout in non-interactive mode
        print_json(meta)

    # Return for validation decorator
    return meta


if __name__ == "__main__":
    main()
