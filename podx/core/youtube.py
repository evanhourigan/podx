"""Core YouTube integration engine - pure business logic.

No UI dependencies, no CLI concerns. Just YouTube video downloading and metadata extraction.
Handles audio extraction, metadata parsing, and episode format conversion.
"""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from ..logging import get_logger

logger = get_logger(__name__)


class YouTubeError(Exception):
    """Raised when YouTube operations fail."""

    pass


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats.

    Args:
        url: YouTube URL

    Returns:
        Video ID string

    Raises:
        YouTubeError: If video ID cannot be extracted
    """
    # Common YouTube URL patterns
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/watch\?.*?v=([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise YouTubeError(f"Could not extract video ID from YouTube URL: {url}")


def is_youtube_url(url: str) -> bool:
    """Check if a URL is a YouTube URL.

    Args:
        url: URL to check

    Returns:
        True if URL is a YouTube URL
    """
    youtube_domains = ["youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"]

    try:
        parsed = urlparse(url)
        return parsed.netloc.lower() in youtube_domains
    except Exception:
        return False


def is_playlist_url(url: str) -> bool:
    """Check if a URL is a YouTube playlist URL.

    Args:
        url: URL to check

    Returns:
        True if URL is a playlist URL
    """
    return "playlist" in url.lower() or "list=" in url


def format_upload_date(upload_date: Optional[str]) -> Optional[str]:
    """Convert YouTube upload date (YYYYMMDD) to RFC format.

    Args:
        upload_date: YouTube upload date string (YYYYMMDD)

    Returns:
        RFC formatted date string, or None if invalid
    """
    if not upload_date or len(upload_date) != 8:
        return None

    try:
        from datetime import datetime

        dt = datetime.strptime(upload_date, "%Y%m%d")
        return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
    except ValueError:
        return None


class YouTubeEngine:
    """Pure YouTube integration logic with no UI dependencies.

    Handles video metadata extraction, audio downloading, and episode format conversion.
    Uses yt-dlp for YouTube interactions.

    Can be used by CLI, web API, or any other interface.
    """

    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """Initialize YouTube engine.

        Args:
            progress_callback: Optional callback for progress updates
        """
        self.progress_callback = progress_callback

    def _report_progress(self, message: str) -> None:
        """Report progress via callback if available."""
        if self.progress_callback:
            self.progress_callback(message)

    def get_metadata(self, url: str) -> Dict[str, Any]:
        """Extract metadata from YouTube video without downloading.

        Args:
            url: YouTube video URL

        Returns:
            Dict containing video metadata

        Raises:
            YouTubeError: If metadata extraction fails
        """
        try:
            import yt_dlp

            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(url, download=False)

                return {
                    "video_id": info.get("id"),
                    "title": info.get("title"),
                    "channel": info.get("uploader") or info.get("channel"),
                    "channel_id": info.get("uploader_id") or info.get("channel_id"),
                    "description": info.get("description"),
                    "upload_date": info.get("upload_date"),  # Format: YYYYMMDD
                    "duration": info.get("duration"),  # Duration in seconds
                    "view_count": info.get("view_count"),
                    "thumbnail": info.get("thumbnail"),
                    "webpage_url": info.get("webpage_url"),
                }
        except ImportError:
            raise YouTubeError(
                "yt-dlp library not installed. Install with: pip install yt-dlp"
            )
        except Exception as e:
            raise YouTubeError(f"Failed to extract YouTube metadata: {e}") from e

    def get_playlist_videos(self, url: str) -> List[Dict[str, Any]]:
        """Extract video list from a YouTube playlist.

        Args:
            url: YouTube playlist URL

        Returns:
            List of dicts with video metadata (id, title, upload_date, duration, url)

        Raises:
            YouTubeError: If playlist extraction fails
        """
        self._report_progress("Fetching playlist...")

        try:
            import yt_dlp

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,  # Don't download, just get info
                "ignoreerrors": True,  # Skip unavailable videos
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    raise YouTubeError("Failed to extract playlist information")

                entries = info.get("entries", [])
                videos = []

                for entry in entries:
                    if entry is None:
                        continue  # Skip unavailable videos

                    videos.append(
                        {
                            "video_id": entry.get("id"),
                            "title": entry.get("title", "Unknown"),
                            "upload_date": entry.get("upload_date"),
                            "duration": entry.get("duration"),
                            "url": entry.get("url")
                            or f"https://www.youtube.com/watch?v={entry.get('id')}",
                            "channel": entry.get("uploader") or entry.get("channel"),
                        }
                    )

                logger.info(
                    "Playlist extracted",
                    playlist_title=info.get("title"),
                    count=len(videos),
                )
                return videos

        except ImportError:
            raise YouTubeError(
                "yt-dlp library not installed. Install with: pip install yt-dlp"
            )
        except Exception as e:
            raise YouTubeError(f"Failed to extract playlist: {e}") from e

    def download_audio(
        self,
        url: str,
        output_dir: Path,
        filename: Optional[str] = None,
        download_progress_callback: Optional[
            Callable[[int, Optional[int]], None]
        ] = None,
    ) -> Dict[str, Any]:
        """Download audio from YouTube video and return metadata.

        Args:
            url: YouTube video URL
            output_dir: Directory to save audio file
            filename: Optional custom filename (defaults to sanitized title)
            download_progress_callback: Optional callback(downloaded_bytes, total_bytes)

        Returns:
            Dict containing episode metadata

        Raises:
            YouTubeError: If download fails
        """
        logger.info("Starting YouTube audio download", url=url)
        self._report_progress("Fetching video metadata")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Get metadata first
        metadata = self.get_metadata(url)

        # Determine filename
        if not filename:
            filename = "audio.%(ext)s"

        # Configure yt-dlp options
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(output_dir / filename),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }

        # Add progress hook if callback provided
        if download_progress_callback:

            def yt_progress_hook(d: Dict[str, Any]) -> None:
                if d["status"] == "downloading":
                    downloaded = d.get("downloaded_bytes", 0)
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    download_progress_callback(downloaded, total)

            ydl_opts["progress_hooks"] = [yt_progress_hook]

        try:
            import yt_dlp

            self._report_progress("Downloading audio")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Find the downloaded file (try multiple formats)
            audio_extensions = ["*.mp3", "*.m4a", "*.webm", "*.ogg"]
            audio_files: List[Path] = []
            for ext in audio_extensions:
                audio_files.extend(output_dir.glob(ext))

            if not audio_files:
                # List all files in the directory for debugging
                all_files = list(output_dir.glob("*"))
                raise YouTubeError(
                    f"Downloaded audio file not found. Files in directory: {[f.name for f in all_files]}"
                )

            audio_path = audio_files[-1]  # Get the most recently created file

            logger.info(
                "YouTube audio download completed",
                audio_path=str(audio_path),
                file_size=audio_path.stat().st_size,
            )

            # Create episode metadata in podx format
            episode_meta = {
                "show": metadata["channel"],
                "episode_title": metadata["title"],
                "episode_published": format_upload_date(metadata.get("upload_date")),
                "audio_path": str(audio_path),
                "image_url": metadata.get("thumbnail"),
                "video_url": url,
                "video_id": metadata["video_id"],
                "duration_seconds": metadata.get("duration"),
                "description": metadata.get("description"),
            }

            return episode_meta

        except ImportError:
            raise YouTubeError(
                "yt-dlp library not installed. Install with: pip install yt-dlp"
            )
        except Exception as e:
            raise YouTubeError(f"Failed to download YouTube audio: {e}") from e

    def fetch_episode(
        self,
        url: str,
        workdir: Path,
        download_progress_callback: Optional[
            Callable[[int, Optional[int]], None]
        ] = None,
    ) -> Dict[str, Any]:
        """Fetch a YouTube video as an episode.

        Downloads audio, extracts metadata, and saves episode-meta.json.

        Args:
            url: YouTube video URL
            workdir: Working directory to save files
            download_progress_callback: Optional callback(downloaded_bytes, total_bytes)

        Returns:
            Dict containing episode metadata

        Raises:
            YouTubeError: If URL is invalid or fetch fails
        """
        if not is_youtube_url(url):
            raise YouTubeError(f"Not a valid YouTube URL: {url}")

        logger.info("Processing YouTube URL", url=url)

        # Download audio and get metadata
        episode_meta = self.download_audio(
            url, workdir, download_progress_callback=download_progress_callback
        )

        # Save episode metadata
        meta_file = workdir / "episode-meta.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(episode_meta, f, indent=2, ensure_ascii=False)

        logger.info("YouTube episode metadata saved", meta_file=str(meta_file))

        return episode_meta


# Convenience functions for direct use
def get_youtube_metadata(url: str) -> Dict[str, Any]:
    """Extract metadata from YouTube video without downloading.

    Args:
        url: YouTube video URL

    Returns:
        Dict containing video metadata
    """
    engine = YouTubeEngine()
    return engine.get_metadata(url)


def download_youtube_audio(
    url: str,
    output_dir: Path,
    filename: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
    download_progress_callback: Optional[Callable[[int, Optional[int]], None]] = None,
) -> Dict[str, Any]:
    """Download audio from YouTube video and return metadata.

    Args:
        url: YouTube video URL
        output_dir: Directory to save audio
        filename: Optional custom filename
        progress_callback: Optional status message callback
        download_progress_callback: Optional callback(downloaded_bytes, total_bytes)

    Returns:
        Dict containing episode metadata
    """
    engine = YouTubeEngine(progress_callback=progress_callback)
    return engine.download_audio(
        url, output_dir, filename, download_progress_callback=download_progress_callback
    )


def fetch_youtube_episode(
    url: str,
    workdir: Path,
    progress_callback: Optional[Callable[[str], None]] = None,
    download_progress_callback: Optional[Callable[[int, Optional[int]], None]] = None,
) -> Dict[str, Any]:
    """Fetch a YouTube video as an episode.

    Args:
        url: YouTube video URL
        workdir: Working directory
        progress_callback: Optional status message callback
        download_progress_callback: Optional callback(downloaded_bytes, total_bytes)

    Returns:
        Dict containing episode metadata
    """
    engine = YouTubeEngine(progress_callback=progress_callback)
    return engine.fetch_episode(
        url, workdir, download_progress_callback=download_progress_callback
    )
