import json
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlparse

import click
import feedparser
import requests
from dateutil import parser as dtparse

from .cli_shared import print_json
from .errors import NetworkError, ValidationError, with_retries
from .logging import get_logger
from .schemas import EpisodeMeta
from .utils import generate_workdir, sanitize_filename
from .validation import validate_output

logger = get_logger(__name__)

UA = "podx/1.0 (+mac cli)"

# Interactive browser imports (optional)
try:
    from rich.console import Console

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Shared UI styling and components
try:
    from .ui import (
        EpisodeBrowser,
        make_console,
        TABLE_BORDER_STYLE,
        TABLE_HEADER_STYLE,
        TABLE_NUM_STYLE,
        TABLE_DATE_STYLE,
        TABLE_TITLE_COL_STYLE,
    )
except Exception:
    # Fallback if ui module is not available
    from .ui.fetch_browser import EpisodeBrowser

    def make_console():
        return Console()

    TABLE_BORDER_STYLE = "grey50"
    TABLE_HEADER_STYLE = "bold magenta"
    TABLE_NUM_STYLE = "cyan"
    TABLE_DATE_STYLE = "bright_blue"
    TABLE_TITLE_COL_STYLE = "white"


def _truncate_text(text: str, max_length: int = 80) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


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

    name = sanitize_filename(entry.get("title", "episode")) + extension
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
        # For interactive mode, exit cleanly with a friendly message
        if interactive:
            click.echo("Error: --interactive requires either --show or --rss-url.", err=True)
            raise SystemExit(2)
        # For non-interactive, surface a usage error (no traceback)
        raise click.UsageError("Either --show or --rss-url must be provided.")
    if show and rss_url:
        raise click.UsageError("Provide either --show or --rss-url, not both.")

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

    # Parse feed with fallbacks (some hosts require UA or redirects)
    logger.debug("Parsing RSS feed", url=feed_url)
    f = feedparser.parse(feed_url)
    if f.bozo or not f.entries:
        # Try fetching content with a browser-like UA
        try:
            session = requests.Session()
            session.headers.update({"User-Agent": UA})
            r = session.get(feed_url, timeout=30, allow_redirects=True, verify=True)
            r.raise_for_status()
            f = feedparser.parse(r.content)
        except Exception as e:
            # Last resort: surface a clearer error including the underlying reason
            reason = getattr(f, "bozo_exception", None)
            raise ValidationError(
                f"Failed to parse feed: {feed_url}"
                + (f" (reason: {reason})" if reason else "")
            ) from e
    if not f.entries:
        raise ValidationError(f"No episodes found in feed: {feed_url}")

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
        workdir = generate_workdir(show_name, episode_date)

    # Download audio
    audio_path = download_enclosure(ep, workdir)

    # Build metadata
    meta: EpisodeMeta = {
        "show": show_name,
        "feed": feed_url,
        "episode_title": ep.get("title", ""),
        "episode_published": (ep.get("published") or ep.get("updated") or ""),
        "audio_path": str(audio_path.resolve()),  # Always use absolute path
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
