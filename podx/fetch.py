import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import click
import feedparser
import requests
from dateutil import parser as dtparse

from .cli_shared import print_json, read_stdin_json
from .schemas import EpisodeMeta

UA = "podx/1.0 (+mac cli)"


def _sanitize(s: str) -> str:
    return re.sub(r"[^\w\-.]+", "_", s.strip())


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


def find_feed_for_show(show_name: str) -> str:
    q = {"media": "podcast", "term": show_name}
    url = "https://itunes.apple.com/search?" + urlencode(q)
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if not results:
        raise SystemExit(f"No podcasts found for: {show_name}")
    feed_url = results[0].get("feedUrl")
    if not feed_url:
        raise SystemExit("Found podcast but no feedUrl.")
    return feed_url


def choose_episode(entries, date_str: Optional[str], title_contains: Optional[str]):
    if title_contains:
        for e in entries:
            if title_contains.lower() in (e.get("title", "").lower()):
                return e
    if date_str:
        want = dtparse.parse(date_str)
        best = None
        best_delta = None
        for e in entries:
            d = e.get("published") or e.get("updated")
            if not d:
                continue
            try:
                dt = dtparse.parse(d)
            except Exception:
                continue
            delta = abs((dt - want).total_seconds())
            if best is None or delta < best_delta:
                best, best_delta = e, delta
        if best:
            return best
    return entries[0] if entries else None


def download_enclosure(entry, out_dir: Path) -> Path:
    links = entry.get("links", []) or []
    audio = None
    for ln in links:
        if ln.get("rel") == "enclosure" and "audio" in (ln.get("type") or ""):
            audio = ln.get("href")
            break
    audio = audio or entry.get("link")
    if not audio:
        raise SystemExit("No audio enclosure found.")
    out_dir.mkdir(parents=True, exist_ok=True)
    name = _sanitize(entry.get("title", "episode")) + Path(audio).suffix
    dest = out_dir / name
    with requests.get(audio, stream=True, headers={"User-Agent": UA}) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if chunk:
                    f.write(chunk)
    return dest


@click.command()
@click.option("--show", help="Podcast show name (iTunes search).")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show).")
@click.option("--date", help="Episode date (YYYY-MM-DD). Picks nearest.")
@click.option("--title-contains", help="Substring to match in episode title.")
@click.option(
    "--outdir", default="episodes", show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--auto-workdir",
    is_flag=True,
    help="Auto-generate workdir based on show name and date",
)
def main(show, rss_url, date, title_contains, outdir, auto_workdir):
    """Find feed, choose episode, download audio. Prints EpisodeMeta JSON to stdout."""
    # Validate that either show or rss_url is provided
    if not show and not rss_url:
        raise SystemExit("Either --show or --rss-url must be provided.")
    if show and rss_url:
        raise SystemExit("Provide either --show or --rss-url, not both.")

    # Get feed URL
    if rss_url:
        feed_url = rss_url
        show_name = None  # Will be extracted from feed
    else:
        feed_url = find_feed_for_show(show)
        show_name = show

    # Parse feed
    f = feedparser.parse(feed_url)
    if f.bozo:
        raise SystemExit(f"Failed to parse feed: {feed_url}")

    # Extract show name from feed if not provided
    if not show_name:
        show_name = f.feed.get("title", "Unknown Show")

    # Choose episode
    ep = choose_episode(f.entries, date, title_contains)
    if not ep:
        raise SystemExit("No episode found.")

    # Determine output directory
    if auto_workdir:
        episode_date = ep.get("published") or ep.get("updated") or date or "unknown"
        workdir = _generate_workdir(show_name, episode_date)
    else:
        workdir = outdir

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

    print_json(meta)


if __name__ == "__main__":
    main()
