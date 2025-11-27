"""CLI wrapper for fetch command.

Simplified v4.0 command for downloading podcast episodes.
"""

import sys
from pathlib import Path
from typing import Optional

import click

from podx.core.fetch import FetchError, PodcastFetcher
from podx.domain.exit_codes import ExitCode
from podx.errors import NetworkError, ValidationError
from podx.logging import get_logger

logger = get_logger(__name__)


@click.command()
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
    Sources (pick one):
      --show TEXT    Search iTunes for podcast by name
      --rss TEXT     Direct RSS feed URL
      --url TEXT     YouTube/Vimeo URL (via yt-dlp)

    \b
    Filtering (optional):
      --date TEXT    Episode date (YYYY-MM-DD) - picks nearest
      --title TEXT   Substring to match in episode title

    \b
    Examples:
      podx fetch --show "Lex Fridman"
      podx fetch --show "Huberman Lab" --date 2024-11-24
      podx fetch --rss "https://example.com/feed.xml"
      podx fetch --url "https://youtube.com/watch?v=xyz"

    Creates a directory structure:
      Show_Name/2024-11-24-episode-slug/
        audio.mp3
        audio.wav        (transcoded for ASR)
        episode-meta.json
    """
    # Count sources provided
    sources = sum(1 for s in [show, rss, url] if s)

    if sources == 0:
        click.echo("podx fetch: provide --show, --rss, or --url", err=True)
        sys.exit(ExitCode.USER_ERROR)

    if sources > 1:
        click.echo("podx fetch: provide only one source (--show, --rss, or --url)", err=True)
        sys.exit(ExitCode.USER_ERROR)

    # Handle YouTube/video URL
    if url:
        try:
            from podx.core.youtube import YouTubeDownloader, is_youtube_url

            if not is_youtube_url(url):
                click.echo("Note: URL doesn't look like YouTube, trying yt-dlp anyway...")

            click.echo(f"Downloading from URL: {url}")

            downloader = YouTubeDownloader()
            result = downloader.download(url)

            audio_path = result.get("audio_path")
            meta = result.get("meta", {})

            click.echo(f"Downloaded: {meta.get('title', 'Unknown')}")
            if audio_path:
                click.echo(f"  Audio: {audio_path}")

            sys.exit(ExitCode.SUCCESS)

        except ImportError:
            click.echo("podx fetch: yt-dlp not installed", err=True)
            click.echo("Install with: pip install yt-dlp", err=True)
            sys.exit(ExitCode.USER_ERROR)
        except Exception as e:
            click.echo(f"podx fetch: {e}", err=True)
            sys.exit(ExitCode.PROCESSING_ERROR)

    # Handle podcast (show or RSS)
    click.echo(f"Fetching podcast: {show or rss}")
    if date:
        click.echo(f"Date filter: {date}")
    if title_contains:
        click.echo(f"Title filter: {title_contains}")

    try:
        fetcher = PodcastFetcher()
        result = fetcher.fetch_episode(
            show_name=show,
            rss_url=rss,
            date=date,
            title_contains=title_contains,
            output_dir=None,  # Use smart naming
        )
    except ValidationError as e:
        click.echo(f"podx fetch: {e}", err=True)
        sys.exit(ExitCode.USER_ERROR)
    except NetworkError as e:
        click.echo(f"podx fetch: {e}", err=True)
        sys.exit(ExitCode.SYSTEM_ERROR)
    except FetchError as e:
        click.echo(f"podx fetch: {e}", err=True)
        sys.exit(ExitCode.PROCESSING_ERROR)

    # Extract metadata from result
    meta = result.get("meta", {})
    audio_path = result.get("audio_path")
    episode_dir = Path(audio_path).parent if audio_path else None

    # Show completion
    click.echo(f"Downloaded: {meta.get('title', 'Unknown')}")
    click.echo(f"  Show: {meta.get('show_name', 'Unknown')}")
    if audio_path:
        click.echo(f"  Audio: {audio_path}")
    if episode_dir:
        click.echo(f"  Directory: {episode_dir}")

    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
