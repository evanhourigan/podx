#!/usr/bin/env python3
"""
YouTube video fetching and processing for podx.
Handles downloading audio, extracting metadata, and integrating with the pipeline.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import yt_dlp
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .errors import NetworkError, ValidationError
from .logging import get_logger
from .schemas import EpisodeMeta

logger = get_logger()
console = Console()


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    # Common YouTube URL patterns
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/watch\?.*?v=([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise ValidationError(f"Could not extract video ID from YouTube URL: {url}")


def get_youtube_metadata(url: str) -> Dict[str, Any]:
    """Extract metadata from YouTube video without downloading."""
    try:
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
    except Exception as e:
        raise NetworkError(f"Failed to extract YouTube metadata: {e}")


def download_youtube_audio(
    url: str, output_dir: Path, filename: Optional[str] = None
) -> Dict[str, Any]:
    """Download audio from YouTube video and return metadata."""
    logger.info("Starting YouTube audio download", url=url)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get metadata first
    metadata = get_youtube_metadata(url)

    # Determine filename
    if not filename:
        # Sanitize title for filename
        safe_title = re.sub(r"[^\w\s-]", "", metadata["title"])
        safe_title = re.sub(r"[-\s]+", "_", safe_title)
        filename = f"{safe_title}.%(ext)s"

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

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Downloading YouTube audio...", total=None)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        # Find the downloaded file (try multiple formats)
        audio_extensions = ["*.mp3", "*.m4a", "*.webm", "*.ogg"]
        audio_files = []
        for ext in audio_extensions:
            audio_files.extend(output_dir.glob(ext))

        if not audio_files:
            # List all files in the directory for debugging
            all_files = list(output_dir.glob("*"))
            raise NetworkError(
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
            "episode_published": _format_upload_date(metadata.get("upload_date")),
            "audio_path": str(audio_path),
            "image_url": metadata.get("thumbnail"),
            "video_url": url,
            "video_id": metadata["video_id"],
            "duration_seconds": metadata.get("duration"),
            "description": metadata.get("description"),
        }

        return episode_meta

    except Exception as e:
        raise NetworkError(f"Failed to download YouTube audio: {e}")


def _format_upload_date(upload_date: Optional[str]) -> Optional[str]:
    """Convert YouTube upload date (YYYYMMDD) to RFC format."""
    if not upload_date or len(upload_date) != 8:
        return None

    try:
        from datetime import datetime

        dt = datetime.strptime(upload_date, "%Y%m%d")
        return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
    except ValueError:
        return None


def is_youtube_url(url: str) -> bool:
    """Check if a URL is a YouTube URL."""
    youtube_domains = ["youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"]

    try:
        parsed = urlparse(url)
        return parsed.netloc.lower() in youtube_domains
    except Exception:
        return False


def fetch_youtube_episode(url: str, workdir: Path) -> Dict[str, Any]:
    """
    Main function to fetch a YouTube video as an episode.
    Returns episode metadata in the same format as RSS episodes.
    """
    if not is_youtube_url(url):
        raise ValidationError(f"Not a valid YouTube URL: {url}")

    logger.info("Processing YouTube URL", url=url)

    # Download audio and get metadata
    episode_meta = download_youtube_audio(url, workdir)

    # Save episode metadata
    meta_file = workdir / "episode-meta.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(episode_meta, f, indent=2, ensure_ascii=False)

    logger.info("YouTube episode metadata saved", meta_file=str(meta_file))

    return episode_meta


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python youtube.py <youtube_url>")
        sys.exit(1)

    url = sys.argv[1]
    output_dir = Path("./youtube_test")

    try:
        result = fetch_youtube_episode(url, output_dir)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
