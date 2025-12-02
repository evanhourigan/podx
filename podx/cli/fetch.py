"""CLI wrapper for fetch command.

Simplified v4.0 command for downloading podcast episodes.
Supports interactive mode with simple numbered selection.
"""

import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import click
from rich.console import Console

from podx.core.fetch import FetchError, PodcastFetcher
from podx.core.transcode import TranscodeEngine, TranscodeError
from podx.domain.exit_codes import ExitCode
from podx.errors import NetworkError, ValidationError
from podx.logging import get_logger
from podx.ui.download_progress import DownloadProgress

logger = get_logger(__name__)
console = Console()

# Pagination settings
ITEMS_PER_PAGE = 10


def _make_download_progress() -> (
    Tuple[DownloadProgress, Callable[[int, Optional[int]], None]]
):
    """Create a download progress tracker and callback.

    Returns:
        Tuple of (progress_instance, callback_function)
    """
    progress = DownloadProgress("Downloading")

    def callback(downloaded: int, total: Optional[int]) -> None:
        if progress.total_size is None and total:
            progress.set_total(total)
        # Only update display (don't re-add downloaded bytes)
        progress.downloaded = downloaded
        progress._display()

    return progress, callback


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


def _get_terminal_width() -> int:
    """Get terminal width, with a sensible default."""
    return shutil.get_terminal_size().columns


def _display_list(
    items: List[Dict[str, Any]],
    page: int,
    format_fn: Callable[[Dict[str, Any], int], str],
    title: str,
) -> int:
    """Display a paginated list with navigation.

    Returns total pages.
    """
    total = len(items)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    start = page * ITEMS_PER_PAGE
    end = min(start + ITEMS_PER_PAGE, total)

    term_width = _get_terminal_width()
    console.print(f"\n[bold cyan]{title}[/bold cyan] (page {page + 1}/{total_pages})\n")

    for idx, item in enumerate(items[start:end], start=start + 1):
        formatted = format_fn(item, term_width)
        console.print(f"  [bold]{idx:3}[/bold]  {formatted}")

    console.print()
    console.print(
        "[dim]Enter number to select • n next • p prev • b back • q quit[/dim]"
    )

    return total_pages


def _format_show(show: Dict[str, Any], max_width: int = 80) -> str:
    """Format a podcast show for display.

    Single line: "Show name [dim]by Artist (N episodes)[/dim]"
    Wraps if too long.
    """
    content_width = max_width - 7  # Account for "  123  " prefix

    name = show.get("collectionName", "Unknown")
    artist = show.get("artistName", "")
    count = show.get("trackCount", 0)

    suffix = f" [dim]by {artist} ({count} episodes)[/dim]"
    plain_len = len(name) + 4 + len(artist) + 15  # approximate

    if plain_len <= content_width:
        return f"{name}{suffix}"

    # Wrap to two lines
    if len(name) > content_width:
        name = name[: content_width - 3] + "..."
    return f"{name}\n       [dim]by {artist} ({count} episodes)[/dim]"


def _format_episode(entry: Dict[str, Any], max_width: int = 80) -> str:
    """Format an episode for display.

    Single line: "Title [dim](date)[/dim]"
    Wraps if too long.
    """
    content_width = max_width - 7  # Account for "  123  " prefix

    title = entry.get("title", "Unknown")
    date = entry.get("published", entry.get("updated", ""))
    if date:
        # Try to extract just the date part
        try:
            from dateutil import parser as dtparse

            parsed = dtparse.parse(date)
            date = parsed.strftime("%Y-%m-%d")
        except Exception:
            date = date[:10] if len(date) >= 10 else date

    single_line = f"{title} [dim]({date})[/dim]"
    plain_len = len(title) + len(date) + 3

    if plain_len <= content_width:
        return single_line

    # Wrap to two lines
    if len(title) > content_width:
        title = title[: content_width - 3] + "..."
    return f"{title}\n       [dim]{date}[/dim]"


def _format_video(video: Dict[str, Any], max_width: int = 80) -> str:
    """Format a YouTube video for display.

    Single line: "Title [dim](date • channel)[/dim]"
    Wraps if too long.
    """
    content_width = max_width - 7  # Account for "  123  " prefix

    title = video.get("title", "Unknown")
    upload_date = video.get("upload_date", "")
    if upload_date and len(upload_date) == 8:
        # Format YYYYMMDD to YYYY-MM-DD
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    channel = video.get("channel", "")

    if channel:
        suffix = f" [dim]({upload_date} • {channel})[/dim]"
        plain_len = len(title) + len(upload_date) + len(channel) + 7
    else:
        suffix = f" [dim]({upload_date})[/dim]"
        plain_len = len(title) + len(upload_date) + 3

    if plain_len <= content_width:
        return f"{title}{suffix}"

    # Wrap to two lines
    if len(title) > content_width:
        title = title[: content_width - 3] + "..."
    if channel:
        return f"{title}\n       [dim]{upload_date} • {channel}[/dim]"
    return f"{title}\n       [dim]{upload_date}[/dim]"


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
) -> Union[Dict[str, Any], str, None]:
    """Interactive episode selection from feed.

    Returns selected episode entry, "back" string, or None if cancelled.
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


def _interactive_video_selection(
    videos: List[Dict[str, Any]],
    playlist_title: str,
) -> Optional[Dict[str, Any]]:
    """Interactive video selection from playlist.

    Returns selected video dict or None if cancelled.
    """
    page = 0

    while True:
        total_pages = _display_list(
            videos, page, _format_video, f"Videos from {playlist_title}"
        )

        try:
            choice = input("\n> ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return None

        if choice in ("q", "quit"):
            return None
        elif choice in ("b", "back"):
            return None  # No "back" in playlist context, just quit
        elif choice == "n" and page < total_pages - 1:
            page += 1
        elif choice == "p" and page > 0:
            page -= 1
        else:
            try:
                sel = int(choice)
                if 1 <= sel <= len(videos):
                    return videos[sel - 1]
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
            elif isinstance(episode, str):
                # Handle any other string returns
                continue

            # Step 3: Download
            # episode is Dict[str, Any] at this point
            episode_dict: Dict[str, Any] = episode
            console.print(
                f"\n[cyan]Downloading:[/cyan] {episode_dict.get('title', 'Unknown')}"
            )

            try:
                # Download audio
                from podx.utils import generate_workdir

                episode_date = (
                    episode_dict.get("published")
                    or episode_dict.get("updated")
                    or "unknown"
                )
                episode_title = episode_dict.get("title", "")
                output_dir = generate_workdir(show_name, episode_date, episode_title)

                progress, progress_callback = _make_download_progress()
                audio_path = fetcher.download_audio(
                    episode_dict, output_dir, progress_callback=progress_callback
                )
                progress.finish()

                # Transcode to WAV for ASR
                _transcode_to_wav(audio_path)

                # Build and save metadata
                import json

                meta = {
                    "show": show_name,
                    "feed": feed_url,
                    "episode_title": episode_dict.get("title", ""),
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
@click.option("--date", help="Episode date filter (YYYY-MM-DD)")
@click.option("--title", "title_contains", help="Substring to match in episode title")
@click.option("--url", help="Video/playlist URL (YouTube, etc.)")
def main(
    show: Optional[str],
    rss: Optional[str],
    date: Optional[str],
    title_contains: Optional[str],
    url: Optional[str],
) -> None:
    """Download podcast episodes.

    \b
    Interactive:
      No options              Search for show, then browse episodes
      --show or --rss         Browse episodes from that show/feed
      --url (playlist)        Browse videos from YouTube playlist

    \b
    Direct download:
      --show + (--date or --title)   Download matching episode
      --url (single video)           Download that video

    \b
    Examples - Interactive:
      podx fetch                                # Search and browse
      podx fetch --show "Lex Fridman"           # Browse show episodes
      podx fetch --rss "https://feed.url/rss"   # Browse from RSS
      podx fetch --url "https://youtube.com/playlist?list=xyz"  # Browse playlist

    \b
    Examples - Direct download:
      podx fetch --show "Huberman Lab" --date 2024-11-24
      podx fetch --show "Lex Fridman" --title "Sam Altman"
      podx fetch --url "https://youtube.com/watch?v=xyz"
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
            from podx.core.youtube import YouTubeEngine, is_playlist_url, is_youtube_url
            from podx.utils import generate_workdir

            if not is_youtube_url(url):
                console.print(
                    "[yellow]Note:[/yellow] URL doesn't look like YouTube, trying yt-dlp anyway..."
                )

            engine = YouTubeEngine()

            # Check if this is a playlist URL - if so, show interactive browser
            if is_playlist_url(url):
                console.print(f"[cyan]Loading playlist:[/cyan] {url}")

                videos = engine.get_playlist_videos(url)
                if not videos:
                    console.print("[red]Error:[/red] No videos found in playlist")
                    sys.exit(ExitCode.USER_ERROR)

                # Interactive video selection
                selected_video = _interactive_video_selection(videos, "Playlist")
                if selected_video is None:
                    console.print("[dim]Cancelled[/dim]")
                    sys.exit(0)

                # Use the selected video's URL
                url = selected_video["url"]
                console.print(
                    f"\n[cyan]Downloading:[/cyan] {selected_video.get('title', 'Unknown')}"
                )

            else:
                console.print(f"[cyan]Downloading from URL:[/cyan] {url}")

            # Get metadata first to determine workdir
            meta = engine.get_metadata(url)
            workdir = generate_workdir(
                meta.get("channel", "YouTube"),
                meta.get("upload_date", "unknown"),
                meta.get("title", "video"),
            )

            progress, progress_callback = _make_download_progress()
            result = {
                "meta": engine.fetch_episode(
                    url, workdir, download_progress_callback=progress_callback
                ),
                "audio_path": None,
            }
            progress.finish()
            # Find audio path from workdir
            for ext in [".mp3", ".m4a", ".wav"]:
                audio_files = list(workdir.glob(f"*{ext}"))
                if audio_files:
                    result["audio_path"] = str(audio_files[0])
                    break

            audio_path = result.get("audio_path")
            if audio_path:
                _transcode_to_wav(Path(audio_path))

            meta = result.get("meta", {})

            console.print(
                f"\n[green]✓ Downloaded:[/green] {meta.get('episode_title', meta.get('title', 'Unknown'))}"
            )
            if audio_path:
                console.print(f"  Audio: {audio_path}")
            console.print(f"  Directory: {workdir}")

            sys.exit(ExitCode.SUCCESS)

        except ImportError:
            console.print("[red]Error:[/red] yt-dlp not installed")
            console.print("[dim]Install with: pip install yt-dlp[/dim]")
            sys.exit(ExitCode.USER_ERROR)
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)
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
            progress, progress_callback = _make_download_progress()
            result = fetcher.fetch_episode(
                show_name=show,
                rss_url=rss,
                date=date,
                title_contains=title_contains,
                output_dir=None,
                progress_callback=progress_callback,
            )
            progress.finish()
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
                    shows = fetcher.search_podcasts(show or "")
                    if not shows:
                        console.print(
                            f"[red]Error:[/red] No podcasts found for '{show}'"
                        )
                        sys.exit(ExitCode.USER_ERROR)
                    # Use first result
                    selected_show = shows[0]
                    feed_url = selected_show.get("feedUrl")  # type: ignore[assignment]
                    show_name = str(selected_show.get("collectionName", show) or "")
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
                fetcher, feed_url, show_name or show or ""
            )

            if episode is None:
                console.print("[dim]Cancelled[/dim]")
                sys.exit(0)
            elif isinstance(episode, str):
                # "back" or other string - exit for browse mode
                console.print("[dim]Cancelled[/dim]")
                sys.exit(0)

            # episode is Dict[str, Any] at this point
            episode_dict: Dict[str, Any] = episode

            # Download selected episode
            console.print(
                f"\n[cyan]Downloading:[/cyan] {episode_dict.get('title', 'Unknown')}"
            )

            import json

            from podx.utils import generate_workdir

            episode_date = (
                episode_dict.get("published")
                or episode_dict.get("updated")
                or "unknown"
            )
            episode_title = episode_dict.get("title", "")
            output_dir = generate_workdir(
                show_name or show or "", episode_date, episode_title
            )

            progress, progress_callback = _make_download_progress()
            audio_path = fetcher.download_audio(
                episode_dict, output_dir, progress_callback=progress_callback
            )
            progress.finish()

            # Transcode to WAV for ASR
            _transcode_to_wav(audio_path)

            meta = {
                "show": show_name or show,
                "feed": feed_url,
                "episode_title": episode_dict.get("title", ""),
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
