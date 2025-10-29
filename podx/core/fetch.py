"""Core podcast fetching engine - pure business logic.

No UI dependencies, no CLI concerns. Just podcast discovery and downloading.
"""
import json
import subprocess
from pathlib import Path
from time import sleep
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse

import feedparser
import requests
from dateutil import parser as dtparse

from ..errors import NetworkError, ValidationError, with_retries
from ..logging import get_logger
from ..schemas import EpisodeMeta
from ..utils import sanitize_filename

logger = get_logger(__name__)

# User agent for HTTP requests
USER_AGENT = "podx/1.0 (+mac cli)"


class FetchError(Exception):
    """Raised when podcast fetching fails."""

    pass


class PodcastFetcher:
    """Pure podcast fetching logic with no UI dependencies.

    Can be used by CLI, TUI studio, web API, or any other interface.
    """

    def __init__(self, user_agent: str = USER_AGENT):
        """Initialize podcast fetcher.

        Args:
            user_agent: User agent string for HTTP requests
        """
        self.user_agent = user_agent

    def search_podcasts(self, show_name: str) -> List[Dict[str, Any]]:
        """Search for podcasts using iTunes API.

        Args:
            show_name: Name of show to search for

        Returns:
            List of podcast result dictionaries from iTunes API

        Raises:
            NetworkError: If API request fails
            ValidationError: If no podcasts found
        """
        q = {"media": "podcast", "term": show_name}
        url = "https://itunes.apple.com/search?" + urlencode(q)

        logger.debug("Searching for podcast", show_name=show_name, url=url)

        # Try with requests first
        session = requests.Session()
        session.headers.update({"User-Agent": self.user_agent})

        try:
            r = session.get(url, timeout=30, verify=True)
            r.raise_for_status()
            data = r.json()
            logger.debug(
                "iTunes API response received",
                results_count=len(data.get("results", [])),
            )
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
        ) as e:
            logger.debug("Primary request failed, trying curl fallback", error=str(e))
            # Fallback: use curl via subprocess
            try:
                result = subprocess.run(
                    ["curl", "-s", url], capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0:
                    raise NetworkError(
                        f"curl failed with return code {result.returncode}"
                    )
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

        return results

    @with_retries(retry_on=(requests.exceptions.RequestException, NetworkError))
    def find_feed_url(self, show_name: str) -> str:
        """Find RSS feed URL for a podcast show using iTunes API.

        Args:
            show_name: Name of show to search for

        Returns:
            RSS feed URL

        Raises:
            ValidationError: If no feed URL found
            NetworkError: If API request fails
        """
        results = self.search_podcasts(show_name)

        feed_url = results[0].get("feedUrl")
        if not feed_url:
            raise ValidationError("Found podcast but no feedUrl.")

        logger.info("Found podcast feed", show_name=show_name, feed_url=feed_url)
        return feed_url

    def choose_episode(
        self,
        entries: List[Dict[str, Any]],
        date_str: Optional[str] = None,
        title_contains: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Choose the best matching episode from feed entries.

        Args:
            entries: List of feed entry dictionaries
            date_str: Optional date string to match (picks nearest)
            title_contains: Optional substring to match in title

        Returns:
            Matching episode entry or None if no match
        """
        logger.debug(
            "Choosing episode",
            total_entries=len(entries),
            date_filter=date_str,
            title_filter=title_contains,
        )

        # Priority 1: Title match
        if title_contains:
            for e in entries:
                if title_contains.lower() in (e.get("title", "").lower()):
                    logger.info(
                        "Found episode by title",
                        title=e.get("title", ""),
                        filter=title_contains,
                    )
                    return e

        # Priority 2: Date match (nearest)
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

        # Default: Most recent episode
        if entries:
            logger.info("Using most recent episode", title=entries[0].get("title", ""))
            return entries[0]

        return None

    def download_audio(
        self, entry: Dict[str, Any], output_dir: Path
    ) -> Path:
        """Download audio file from episode entry.

        Args:
            entry: Feed entry with audio enclosure
            output_dir: Directory to save audio file

        Returns:
            Path to downloaded audio file

        Raises:
            ValidationError: If no audio enclosure found
            NetworkError: If download fails after retries
        """
        # Find audio enclosure URL
        links = entry.get("links", []) or []
        audio_url = None
        for ln in links:
            if ln.get("rel") == "enclosure" and "audio" in (ln.get("type") or ""):
                audio_url = ln.get("href")
                break
        audio_url = audio_url or entry.get("link")

        if not audio_url:
            raise ValidationError("No audio enclosure found.")

        logger.debug("Downloading audio", url=audio_url, output_dir=str(output_dir))

        output_dir.mkdir(parents=True, exist_ok=True)

        # Extract clean file extension from URL
        parsed_url = urlparse(audio_url)
        clean_path = parsed_url.path
        extension = Path(clean_path).suffix or ".mp3"  # Default to .mp3

        name = sanitize_filename(entry.get("title", "episode")) + extension
        dest = output_dir / name

        # Download with retries and backoff
        backoffs = [0, 1, 2, 4]
        last_err: Optional[Exception] = None
        for attempt, delay in enumerate(backoffs):
            try:
                if delay:
                    logger.debug("Retrying download", attempt=attempt + 1, delay=delay)
                    sleep(delay)

                with requests.get(
                    audio_url,
                    stream=True,
                    headers={"User-Agent": self.user_agent},
                    timeout=60,
                ) as r:
                    r.raise_for_status()

                    with open(dest, "wb") as f:
                        downloaded = 0
                        for chunk in r.iter_content(chunk_size=1 << 20):  # 1MB chunks
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
                logger.warning(
                    "Download attempt failed", attempt=attempt + 1, error=str(e)
                )
                continue

        if last_err is not None and not dest.exists():
            raise NetworkError(f"Failed to download enclosure: {last_err}")

        return dest

    def parse_feed(self, feed_url: str) -> feedparser.FeedParserDict:
        """Parse RSS feed with fallback strategies.

        Args:
            feed_url: RSS feed URL

        Returns:
            Parsed feed dictionary

        Raises:
            ValidationError: If feed cannot be parsed or has no entries
        """
        logger.debug("Parsing RSS feed", url=feed_url)
        feed = feedparser.parse(feed_url)

        if feed.bozo or not feed.entries:
            # Try fetching with user agent
            try:
                session = requests.Session()
                session.headers.update({"User-Agent": self.user_agent})
                r = session.get(feed_url, timeout=30, allow_redirects=True, verify=True)
                r.raise_for_status()
                feed = feedparser.parse(r.content)
            except Exception as e:
                reason = getattr(feed, "bozo_exception", None)
                raise ValidationError(
                    f"Failed to parse feed: {feed_url}"
                    + (f" (reason: {reason})" if reason else "")
                ) from e

        if not feed.entries:
            raise ValidationError(f"No episodes found in feed: {feed_url}")

        return feed

    def fetch_episode(
        self,
        show_name: Optional[str] = None,
        rss_url: Optional[str] = None,
        date: Optional[str] = None,
        title_contains: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Fetch a podcast episode with smart defaults.

        Args:
            show_name: Podcast show name (will search iTunes for RSS)
            rss_url: Direct RSS feed URL (alternative to show_name)
            date: Episode date (YYYY-MM-DD) for filtering
            title_contains: Substring to match in episode title
            output_dir: Directory to save episode (defaults to smart naming)

        Returns:
            Dictionary with episode metadata, audio path, and directory

        Raises:
            ValidationError: If inputs are invalid or episode not found
            NetworkError: If download fails
            FetchError: For other fetch failures
        """
        # Validate inputs
        if not show_name and not rss_url:
            raise ValidationError("Either show_name or rss_url must be provided")
        if show_name and rss_url:
            raise ValidationError("Provide either show_name or rss_url, not both")

        # Get feed URL
        if rss_url:
            feed_url = rss_url
            extracted_show_name = None
        else:
            feed_url = self.find_feed_url(show_name)
            extracted_show_name = show_name

        # Parse feed
        feed = self.parse_feed(feed_url)

        # Extract show name from feed if needed
        if not extracted_show_name:
            extracted_show_name = feed.feed.get("title", "Unknown Show")
            logger.debug("Extracted show name from feed", show_name=extracted_show_name)

        # Choose episode
        episode = self.choose_episode(feed.entries, date, title_contains)
        if not episode:
            raise ValidationError("No episode found matching criteria")

        # Determine output directory
        if output_dir is None:
            # Use smart naming: show/date/
            episode_date = (
                episode.get("published") or episode.get("updated") or "unknown"
            )
            # Import here to avoid circular dependency
            from ..utils import generate_workdir

            output_dir = generate_workdir(extracted_show_name, episode_date)

        # Download audio
        audio_path = self.download_audio(episode, output_dir)

        # Build metadata
        meta: EpisodeMeta = {
            "show": extracted_show_name,
            "feed": feed_url,
            "episode_title": episode.get("title", ""),
            "episode_published": (
                episode.get("published") or episode.get("updated") or ""
            ),
            "audio_path": str(audio_path.resolve()),
        }

        # Add image URL if available
        if feed.feed.get("image", {}).get("href"):
            meta["image_url"] = feed.feed["image"]["href"]

        # Save metadata to episode directory
        meta_file = output_dir / "episode-meta.json"
        meta_file.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Episode metadata saved", file=str(meta_file))

        return {
            "meta": meta,
            "meta_path": str(meta_file),
            "directory": str(output_dir),
            "audio_path": str(audio_path),
        }


# Convenience functions for direct use
def search_podcasts(show_name: str) -> List[Dict[str, Any]]:
    """Search for podcasts by name.

    Args:
        show_name: Name of show to search for

    Returns:
        List of podcast results from iTunes API
    """
    fetcher = PodcastFetcher()
    return fetcher.search_podcasts(show_name)


def find_feed_url(show_name: str) -> str:
    """Find RSS feed URL for a podcast show.

    Args:
        show_name: Name of show to search for

    Returns:
        RSS feed URL
    """
    fetcher = PodcastFetcher()
    return fetcher.find_feed_url(show_name)


def fetch_episode(
    show_name: Optional[str] = None,
    rss_url: Optional[str] = None,
    date: Optional[str] = None,
    title_contains: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Fetch a podcast episode with smart defaults.

    Args:
        show_name: Podcast show name
        rss_url: Direct RSS feed URL
        date: Episode date for filtering
        title_contains: Title substring to match
        output_dir: Output directory

    Returns:
        Dictionary with episode metadata and paths
    """
    fetcher = PodcastFetcher()
    return fetcher.fetch_episode(show_name, rss_url, date, title_contains, output_dir)
