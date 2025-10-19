"""
Dropbox source plugin for podx.

This plugin allows downloading audio files from Dropbox for podcast processing.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from podx.logging import get_logger
from podx.plugins import PluginMetadata, PluginType, SourcePlugin
from podx.schemas import EpisodeMeta

logger = get_logger(__name__)

try:
    import dropbox
    from dropbox.exceptions import AuthError
    from dropbox.files import FileMetadata

    DROPBOX_AVAILABLE = True
except ImportError:
    DROPBOX_AVAILABLE = False


class DropboxSourcePlugin(SourcePlugin):
    """Source plugin for downloading files from Dropbox."""

    def __init__(self):
        self.initialized = False
        self.dbx = None

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="dropbox-source",
            version="1.0.0",
            description="Download audio files from Dropbox",
            author="Podx Team",
            plugin_type=PluginType.SOURCE,
            dependencies=["dropbox"],
            config_schema={
                "access_token": {
                    "type": "string",
                    "required": True,
                    "description": "Dropbox access token",
                },
                "app_key": {
                    "type": "string",
                    "description": "Dropbox app key (optional, for advanced auth)",
                },
                "app_secret": {
                    "type": "string",
                    "description": "Dropbox app secret (optional, for advanced auth)",
                },
            },
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        if not DROPBOX_AVAILABLE:
            logger.error(
                "dropbox library not available. Install with: pip install dropbox"
            )
            return False

        if "access_token" not in config:
            logger.error("access_token is required in configuration")
            return False

        return True

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        if not DROPBOX_AVAILABLE:
            raise ImportError("dropbox library not available")

        access_token = config["access_token"]

        try:
            self.dbx = dropbox.Dropbox(access_token)
            # Test the connection
            self.dbx.users_get_current_account()

            self.initialized = True
            logger.info("Dropbox source plugin initialized")

        except AuthError as e:
            logger.error("Dropbox authentication failed", error=str(e))
            raise

    def fetch_episode(self, query: Dict[str, Any]) -> EpisodeMeta:
        """
        Download audio file from Dropbox.

        Args:
            query: Should contain 'path' key with Dropbox file path

        Returns:
            EpisodeMeta with downloaded file information
        """
        if not self.initialized:
            raise RuntimeError("Plugin not initialized")

        dropbox_path = query.get("path")
        if not dropbox_path:
            raise ValueError("Dropbox file path required in query")

        output_dir = Path(query.get("output_dir", "."))
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Get file metadata
            metadata = self.dbx.files_get_metadata(dropbox_path)

            if not isinstance(metadata, FileMetadata):
                raise ValueError(f"{dropbox_path} is not a file")

            # Download the file
            filename = Path(metadata.name)
            local_path = output_dir / filename

            logger.info("Downloading from Dropbox", path=dropbox_path, size=metadata.size)

            self.dbx.files_download_to_file(str(local_path), dropbox_path)

            # Extract episode info from filename or query
            episode_title = query.get("title") or filename.stem
            show_name = query.get("show") or "Dropbox Audio"

            # Create EpisodeMeta
            episode_meta = {
                "show": show_name,
                "episode_title": episode_title,
                "release_date": self._format_date(metadata.client_modified),
                "description": query.get("description", ""),
                "duration": 0,  # Unknown until transcoded
                "audio_path": str(local_path),
                "episode_url": self._get_sharing_url(dropbox_path),
                "source": "dropbox",
                "metadata": {
                    "dropbox_path": dropbox_path,
                    "file_size": metadata.size,
                    "modified": str(metadata.server_modified),
                    "content_hash": metadata.content_hash,
                },
            }

            logger.info(
                "File downloaded from Dropbox",
                title=episode_title,
                file=str(local_path),
                size=metadata.size,
            )

            return episode_meta

        except Exception as e:
            logger.error("Dropbox download failed", path=dropbox_path, error=str(e))
            raise

    def supports_query(self, query: Dict[str, Any]) -> bool:
        """Check if this plugin can handle the given query."""
        # Check if it has a Dropbox path
        path = query.get("path", "")
        return bool(path and not path.startswith(("http://", "https://")))

    def list_folder(self, folder_path: str = "") -> list:
        """
        List files in a Dropbox folder.

        Args:
            folder_path: Dropbox folder path (empty for root)

        Returns:
            List of file entries
        """
        if not self.initialized:
            raise RuntimeError("Plugin not initialized")

        try:
            result = self.dbx.files_list_folder(folder_path)
            entries = []

            for entry in result.entries:
                if isinstance(entry, FileMetadata):
                    # Only include audio files
                    if self._is_audio_file(entry.name):
                        entries.append(
                            {
                                "name": entry.name,
                                "path": entry.path_display,
                                "size": entry.size,
                                "modified": str(entry.server_modified),
                            }
                        )

            logger.info(f"Listed {len(entries)} audio files from Dropbox folder", path=folder_path)
            return entries

        except Exception as e:
            logger.error("Failed to list Dropbox folder", path=folder_path, error=str(e))
            raise

    def _is_audio_file(self, filename: str) -> bool:
        """Check if file is an audio file."""
        audio_extensions = {
            ".mp3",
            ".wav",
            ".m4a",
            ".aac",
            ".ogg",
            ".flac",
            ".wma",
            ".opus",
        }
        return Path(filename).suffix.lower() in audio_extensions

    def _format_date(self, dt: datetime) -> str:
        """Format datetime to standard date string."""
        return dt.strftime("%Y-%m-%d")

    def _get_sharing_url(self, path: str) -> str:
        """Get or create a sharing link for the file."""
        try:
            # Try to get existing shared link
            links = self.dbx.sharing_list_shared_links(path=path)
            if links.links:
                return links.links[0].url

            # Create new shared link
            link = self.dbx.sharing_create_shared_link_with_settings(path)
            return link.url

        except Exception as e:
            logger.warning("Failed to create Dropbox sharing link", path=path, error=str(e))
            return ""
