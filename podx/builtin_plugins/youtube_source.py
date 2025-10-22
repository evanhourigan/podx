"""
YouTube source plugin for podx.

This plugin allows downloading and processing YouTube videos as podcast episodes.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from podx.logging import get_logger
from podx.plugins import PluginMetadata, PluginType, SourcePlugin
from podx.schemas import EpisodeMeta

logger = get_logger(__name__)

try:
    import yt_dlp

    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False


class YouTubeSourcePlugin(SourcePlugin):
    """Source plugin for downloading YouTube videos."""

    def __init__(self):
        self.initialized = False

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="youtube-source",
            version="1.0.0",
            description="Download YouTube videos as podcast episodes",
            author="Podx Team",
            plugin_type=PluginType.SOURCE,
            dependencies=["yt-dlp"],
            config_schema={
                "quality": {"type": "string", "default": "bestaudio"},
                "format": {"type": "string", "default": "mp3"},
                "output_template": {"type": "string", "default": "%(title)s.%(ext)s"},
            },
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        if not YTDLP_AVAILABLE:
            logger.error(
                "yt-dlp library not available. Install with: pip install yt-dlp"
            )
            return False

        return True

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        if not YTDLP_AVAILABLE:
            raise ImportError("yt-dlp library not available")

        self.config = config
        self.initialized = True

        logger.info("YouTube source plugin initialized")

    def fetch_episode(self, query: Dict[str, Any]) -> EpisodeMeta:
        """
        Download YouTube video as episode.

        Args:
            query: Should contain 'url' key with YouTube URL

        Returns:
            EpisodeMeta with downloaded video information
        """
        if not self.initialized:
            raise RuntimeError("Plugin not initialized")

        url = query.get("url")
        if not url:
            raise ValueError("YouTube URL required in query")

        output_dir = Path(query.get("output_dir", "."))
        output_dir.mkdir(parents=True, exist_ok=True)

        # Configure yt-dlp options
        ydl_opts = {
            "format": self.config.get("quality", "bestaudio"),
            "outtmpl": str(
                output_dir / self.config.get("output_template", "%(title)s.%(ext)s")
            ),
            "extractaudio": True,
            "audioformat": self.config.get("format", "mp3"),
            "audioquality": "192K",
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video info
                info = ydl.extract_info(url, download=False)

                # Download the video
                ydl.download([url])

                # Construct file path
                audio_filename = ydl.prepare_filename(info)
                # yt-dlp changes extension when extracting audio
                audio_path = Path(audio_filename).with_suffix(
                    f".{self.config.get('format', 'mp3')}"
                )

                # Create EpisodeMeta
                episode_meta = {
                    "show": info.get("uploader", "YouTube"),
                    "episode_title": info.get("title", "Unknown Title"),
                    "release_date": self._parse_upload_date(info.get("upload_date")),
                    "description": info.get("description", ""),
                    "duration": info.get("duration", 0),
                    "audio_path": str(audio_path),
                    "episode_url": url,
                    "source": "youtube",
                    "metadata": {
                        "view_count": info.get("view_count"),
                        "like_count": info.get("like_count"),
                        "uploader": info.get("uploader"),
                        "channel_url": info.get("channel_url"),
                        "tags": info.get("tags", []),
                    },
                }

                logger.info(
                    "YouTube video downloaded",
                    title=episode_meta["episode_title"],
                    duration=episode_meta["duration"],
                    file=str(audio_path),
                )

                return episode_meta

        except Exception as e:
            logger.error("YouTube download failed", url=url, error=str(e))
            raise

    def supports_query(self, query: Dict[str, Any]) -> bool:
        """Check if this plugin can handle the given query."""
        url = query.get("url", "")

        # Check if it's a YouTube URL
        youtube_patterns = [
            r"https?://(?:www\.)?youtube\.com/watch\?v=",
            r"https?://(?:www\.)?youtube\.com/embed/",
            r"https?://youtu\.be/",
            r"https?://(?:www\.)?youtube\.com/playlist\?list=",
        ]

        return any(re.match(pattern, url) for pattern in youtube_patterns)

    def _parse_upload_date(self, upload_date: str) -> str:
        """Parse YouTube upload date to standard format."""
        if not upload_date:
            return datetime.now().strftime("%Y-%m-%d")

        try:
            # YouTube upload_date format is typically YYYYMMDD
            if len(upload_date) == 8:
                year = upload_date[:4]
                month = upload_date[4:6]
                day = upload_date[6:8]
                return f"{year}-{month}-{day}"
        except (ValueError, IndexError):
            pass

        return datetime.now().strftime("%Y-%m-%d")
