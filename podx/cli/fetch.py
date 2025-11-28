"""CLI wrapper for fetch command.

Simplified v4.0 command for downloading podcast episodes.
Supports interactive mode with simple numbered selection.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from rich.console import Console

from podx.core.fetch import FetchError, PodcastFetcher
from podx.core.transcode import TranscodeEngine, TranscodeError
from podx.domain.exit_codes import ExitCode
from podx.errors import NetworkError, ValidationError
from podx.logging import get_logger

logger = get_logger(__name__)
console = Console()

# Pagination settings
ITEMS_PER_PAGE = 10


def _transcode_to_wav(audio_path: Path) -> Optional[Path]:
    """Transcode audio to WAV for ASR. Returns WAV path or None on failure."""
    # Skip if already WAV
    if audio_path.suffix.lower() == ".wav":
        return audio_path

    try:
        engine = TranscodeEngine(format="wav16")
        result = engine.transcode(audio_path)
        wav_path = Path(result["audio_path"])
        console.print(f"[dim]Transcoded to: {wav_path.name}[/dim]")
        return wav_path
    except TranscodeError as e:
        console.print(f"[yellow]Transcode warning:[/yellow] {e}")
        return None


def _display_list(
    items: List[Dict[str, Any]],
    page: int,
    format_fn,
    title: str,
) -> int:
    """Display a paginated list with navigation.

    Returns total pages.
    """
    total = len(items)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    start = page * ITEMS_PER_PAGE
    end = min(start + ITEMS_PER_PAGE, total)

    console.print(f"\n[bold cyan]{title}[/bold cyan] (page {page + 1}/{total_pages})\n")

    for idx, item in enumerate(items[start:end], start=start + 1):
        formatted = format_fn(item)
        console.print(f"  [bold]{idx:3}[/bold]  {formatted}")

    console.print()
    console.print(
        "[dim]Enter number to select • n next • p prev • b back • q quit[/dim]"
    )

    return total_pages


def _format_show(show: Dict[str, Any]) -> str:
    """Format a podcast show for display."""
    name = show.get("collectionName", "Unknown")
    artist = show.get("artistName", "")
    count = show.get("trackCount", 0)
    return f"{name} [dim]by {artist} ({count} episodes)[/dim]"


def _format_episode(entry: Dict[str, Any]) -> str:
    """Format an episode for display."""
    title = entry.get("title", "Unknown")[:60]
    date = entry.get("published", entry.get("updated", ""))
    if date:
        # Try to extract just the date part
        try:
            from dateutil import parser as dtparse

            parsed = dtparse.parse(date)
            date = parsed.strftime("%Y-%m-%d")
        except Exception:
            date = date[:10] if len(date) >= 10 else date
    return f"{title} [dim]{date}[/dim]"


def _interactive_show_selection(fetcher: PodcastFetcher) -> Optional[Dict[str, Any]]:
    """Interactive show search and selection.

    Returns selected show dict or None if cancelled.
    """
    while True:
        console.print("\n[bold]Search for a podcast[/bold]")
        try:
            query = input("Show name: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None

        if not query:
            console.print("[dim]Cancelled[/dim]")
            return None

        console.print(f"[dim]Searching for '{query}'...[/dim]")

        try:
            shows = fetcher.search_podcasts(query)
        except ValidationError as e:
            console.print(f"[yellow]No results:[/yellow] {e}")
            continue
        except NetworkError as e:
            console.print(f"[red]Network error:[/red] {e}")
            continue

        # Paginated show selection
        page = 0
        while True:
            total_pages = _display_list(shows, page, _format_show, "Podcasts found")

            try:
                choice = input("\n> ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return None

            if choice in ("q", "quit"):
                return None
            elif choice in ("b", "back"):
                break  # Go back to search
            elif choice == "n" and page < total_pages - 1:
                page += 1
            elif choice == "p" and page > 0:
                page -= 1
            else:
                try:
                    sel = int(choice)
                    if 1 <= sel <= len(shows):
                        return shows[sel - 1]
                    console.print("[red]Invalid number[/red]")
                except ValueError:
                    console.print("[red]Invalid input[/red]")


def _interactive_episode_selection(
    fetcher: PodcastFetcher,
    feed_url: str,
    show_name: str,
) -> Optional[Dict[str, Any]]:
    """Interactive episode selection from feed.

    Returns selected episode entry or None if cancelled.
    """
    console.print(f"[dim]Loading episodes from {show_name}...[/dim]")

    try:
        feed = fetcher.parse_feed(feed_url)
    except ValidationError as e:
        console.print(f"[red]Error:[/red] {e}")
        return None

    episodes = feed.entries
    page = 0

    while True:
        total_pages = _display_list(
            episodes, page, _format_episode, f"Episodes from {show_name}"
        )

        try:
            choice = input("\n> ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return None

        if choice in ("q", "quit"):
            return None
        elif choice in ("b", "back"):
            return "back"  # Signal to go back to show selection
        elif choice == "n" and page < total_pages - 1:
            page += 1
        elif choice == "p" and page > 0:
            page -= 1
        else:
            try:
                sel = int(choice)
                if 1 <= sel <= len(episodes):
                    return episodes[sel - 1]
                console.print("[red]Invalid number[/red]")
            except ValueError:
                console.print("[red]Invalid input[/red]")


def _run_interactive(fetcher: PodcastFetcher) -> Optional[Dict[str, Any]]:
    """Run full interactive flow: search → select show → select episode → download.

    Returns result dict or None if cancelled.
    """
    while True:
        # Step 1: Select show
        show = _interactive_show_selection(fetcher)
        if show is None:
            return None

        feed_url = show.get("feedUrl")
        show_name = show.get("collectionName", "Unknown")

        if not feed_url:
            console.print("[red]Error:[/red] No RSS feed found for this podcast")
            continue

        # Step 2: Select episode
        while True:
            episode = _interactive_episode_selection(fetcher, feed_url, show_name)

            if episode is None:
                return None
            elif episode == "back":
                break  # Go back to show selection

            # Step 3: Download
            console.print(
                f"\n[cyan]Downloading:[/cyan] {episode.get('title', 'Unknown')}"
            )

            try:
                # Download audio
                from podx.utils import generate_workdir

                episode_date = (
                    episode.get("published") or episode.get("updated") or "unknown"
                )
                episode_title = episode.get("title", "")
                output_dir = generate_workdir(show_name, episode_date, episode_title)

                audio_path = fetcher.download_audio(episode, output_dir)

                # Transcode to WAV for ASR
                _transcode_to_wav(audio_path)

                # Build and save metadata
                import json

                meta = {
                    "show": show_name,
                    "feed": feed_url,
                    "episode_title": episode.get("title", ""),
                    "episode_published": episode_date,
                    "audio_path": str(audio_path.resolve()),
                }

                # Add image URL if available from show
                if show.get("artworkUrl600"):
                    meta["image_url"] = show["artworkUrl600"]

                meta_file = output_dir / "episode-meta.json"
                meta_file.write_text(
                    json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
                )

                return {
                    "meta": meta,
                    "meta_path": str(meta_file),
                    "directory": str(output_dir),
                    "audio_path": str(audio_path),
                }

            except Exception as e:
                console.print(f"[red]Download failed:[/red] {e}")
                # Let them try another episode
                continue


@click.command(context_settings={"max_content_width": 120})
@click.option("--show", help="Podcast show name (searches iTunes)")
@click.option("--rss", help="Direct RSS feed URL")
@click.option("--url", help="Video URL (YouTube, Vimeo, etc. via yt-dlp)")
@click.option("--date", help="Episode date (YYYY-MM-DD)")
@click.option("--title", "title_contains", help="Substring to match in episode title")
def main(
    show: Optional[str],
    rss: Optional[str],
    url: Optional[str],
    date: Optional[str],
    title_contains: Optional[str],
):
    """Download podcast episodes.

    \b
    Without options:
      Fully interactive - search for show, then browse episodes

    \b
    With --show or --rss:
      Opens episode browser - select episode by number

    \b
    With --show + --date or --title:
      Direct download - auto-selects matching episode

    \b
    Navigation keys:
      1-9    Select item by number
      n      Next page
      p      Previous page
      b      Go back
      q      Quit

    \b
    Examples:
      podx fetch                                    # Full interactive
      podx fetch --show "Lex Fridman"               # Browse episodes
      podx fetch --show "Huberman Lab" --date 2024-11-24  # Direct download
      podx fetch --url "https://youtube.com/watch?v=xyz"  # YouTube
    """
    fetcher = PodcastFetcher()

    # No options = interactive mode
    if not any([show, rss, url]):
        try:
            result = _run_interactive(fetcher)
            if result is None:
                console.print("[dim]Cancelled[/dim]")
                sys.exit(0)

            meta = result.get("meta", {})
            console.print(
                f"\n[green]✓ Downloaded:[/green] {meta.get('episode_title', 'Unknown')}"
            )
            console.print(f"  Show: {meta.get('show', 'Unknown')}")
            console.print(f"  Audio: {result.get('audio_path')}")
            console.print(f"  Directory: {result.get('directory')}")
            sys.exit(ExitCode.SUCCESS)

        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)

    # Handle YouTube/video URL
    if url:
        try:
            from podx.core.youtube import YouTubeDownloader, is_youtube_url

            if not is_youtube_url(url):
                console.print(
                    "[yellow]Note:[/yellow] URL doesn't look like YouTube, trying yt-dlp anyway..."
                )

            console.print(f"[cyan]Downloading from URL:[/cyan] {url}")

            downloader = YouTubeDownloader()
            result = downloader.download(url)

            audio_path = result.get("audio_path")
            if audio_path:
                _transcode_to_wav(Path(audio_path))

            meta = result.get("meta", {})

            console.print(
                f"\n[green]✓ Downloaded:[/green] {meta.get('title', 'Unknown')}"
            )
            if audio_path:
                console.print(f"  Audio: {audio_path}")

            sys.exit(ExitCode.SUCCESS)

        except ImportError:
            console.print("[red]Error:[/red] yt-dlp not installed")
            console.print("[dim]Install with: pip install yt-dlp[/dim]")
            sys.exit(ExitCode.USER_ERROR)
        except Exception as e:
            console.print(f"[red]Download Error:[/red] {e}")
            sys.exit(ExitCode.PROCESSING_ERROR)

    # Handle podcast (show or RSS)
    # If --date or --title provided, use direct mode (auto-select episode)
    # Otherwise, show interactive episode browser
    if date or title_contains:
        # Direct mode - auto-select episode
        console.print(f"[cyan]Fetching podcast:[/cyan] {show or rss}")
        if date:
            console.print(f"[cyan]Date filter:[/cyan] {date}")
        if title_contains:
            console.print(f"[cyan]Title filter:[/cyan] {title_contains}")

        try:
            result = fetcher.fetch_episode(
                show_name=show,
                rss_url=rss,
                date=date,
                title_contains=title_contains,
                output_dir=None,
            )
            # Transcode to WAV for ASR
            audio_path = result.get("audio_path")
            if audio_path:
                _transcode_to_wav(Path(audio_path))
        except ValidationError as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(ExitCode.USER_ERROR)
        except NetworkError as e:
            console.print(f"[red]Network Error:[/red] {e}")
            sys.exit(ExitCode.SYSTEM_ERROR)
        except FetchError as e:
            console.print(f"[red]Fetch Error:[/red] {e}")
            sys.exit(ExitCode.PROCESSING_ERROR)
    else:
        # Interactive mode - browse and select episode
        try:
            # Get feed URL
            if rss:
                feed_url = rss
                show_name = None
            else:
                console.print(f"[dim]Searching for '{show}'...[/dim]")
                try:
                    shows = fetcher.search_podcasts(show)
                    if not shows:
                        console.print(
                            f"[red]Error:[/red] No podcasts found for '{show}'"
                        )
                        sys.exit(ExitCode.USER_ERROR)
                    # Use first result
                    selected_show = shows[0]
                    feed_url = selected_show.get("feedUrl")
                    show_name = selected_show.get("collectionName", show)
                    if not feed_url:
                        console.print(
                            "[red]Error:[/red] No RSS feed found for this podcast"
                        )
                        sys.exit(ExitCode.USER_ERROR)
                except ValidationError as e:
                    console.print(f"[red]Error:[/red] {e}")
                    sys.exit(ExitCode.USER_ERROR)
                except NetworkError as e:
                    console.print(f"[red]Network Error:[/red] {e}")
                    sys.exit(ExitCode.SYSTEM_ERROR)

            # Show interactive episode browser
            episode = _interactive_episode_selection(
                fetcher, feed_url, show_name or show
            )

            if episode is None:
                console.print("[dim]Cancelled[/dim]")
                sys.exit(0)
            elif episode == "back":
                console.print("[dim]Cancelled[/dim]")
                sys.exit(0)

            # Download selected episode
            console.print(
                f"\n[cyan]Downloading:[/cyan] {episode.get('title', 'Unknown')}"
            )

            import json

            from podx.utils import generate_workdir

            episode_date = (
                episode.get("published") or episode.get("updated") or "unknown"
            )
            episode_title = episode.get("title", "")
            output_dir = generate_workdir(
                show_name or show, episode_date, episode_title
            )

            audio_path = fetcher.download_audio(episode, output_dir)

            # Transcode to WAV for ASR
            _transcode_to_wav(audio_path)

            meta = {
                "show": show_name or show,
                "feed": feed_url,
                "episode_title": episode.get("title", ""),
                "episode_published": episode_date,
                "audio_path": str(audio_path.resolve()),
            }

            meta_file = output_dir / "episode-meta.json"
            meta_file.write_text(
                json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            result = {
                "meta": meta,
                "meta_path": str(meta_file),
                "directory": str(output_dir),
                "audio_path": str(audio_path),
            }

        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)

    # Extract metadata from result
    meta = result.get("meta", {})
    audio_path = result.get("audio_path")
    episode_dir = Path(audio_path).parent if audio_path else None

    # Show completion
    console.print(
        f"\n[green]✓ Downloaded:[/green] {meta.get('episode_title', 'Unknown')}"
    )
    console.print(f"  Show: {meta.get('show', 'Unknown')}")
    if audio_path:
        console.print(f"  Audio: {audio_path}")
    if episode_dir:
        console.print(f"  Directory: {episode_dir}")

    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
