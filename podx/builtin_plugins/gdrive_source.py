"""
Google Drive source plugin for podx.

This plugin allows downloading audio files from Google Drive for podcast processing.
"""

import io
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from podx.logging import get_logger
from podx.plugins import PluginMetadata, PluginType, SourcePlugin
from podx.schemas import EpisodeMeta

logger = get_logger(__name__)

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False


# Google Drive API scopes
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class GoogleDriveSourcePlugin(SourcePlugin):
    """Source plugin for downloading files from Google Drive."""

    def __init__(self):
        self.initialized = False
        self.service = None
        self.creds = None

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="gdrive-source",
            version="1.0.0",
            description="Download audio files from Google Drive",
            author="Podx Team",
            plugin_type=PluginType.SOURCE,
            dependencies=["google-auth", "google-auth-oauthlib", "google-auth-httplib2", "google-api-python-client"],
            config_schema={
                "credentials_file": {
                    "type": "string",
                    "description": "Path to Google OAuth credentials JSON file",
                },
                "token_file": {
                    "type": "string",
                    "default": "~/.podx/gdrive_token.json",
                    "description": "Path to store OAuth token",
                },
                "service_account_file": {
                    "type": "string",
                    "description": "Path to service account JSON file (alternative to OAuth)",
                },
            },
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        if not GDRIVE_AVAILABLE:
            logger.error(
                "Google Drive libraries not available. "
                "Install with: pip install google-auth google-auth-oauthlib "
                "google-auth-httplib2 google-api-python-client"
            )
            return False

        # Need either credentials file or service account file
        if "credentials_file" not in config and "service_account_file" not in config:
            logger.error(
                "Either credentials_file or service_account_file is required in configuration"
            )
            return False

        return True

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        if not GDRIVE_AVAILABLE:
            raise ImportError("Google Drive libraries not available")

        self.config = config

        # Authenticate and create service
        self.creds = self._authenticate()
        self.service = build("drive", "v3", credentials=self.creds)

        self.initialized = True
        logger.info("Google Drive source plugin initialized")

    def fetch_episode(self, query: Dict[str, Any]) -> EpisodeMeta:
        """
        Download audio file from Google Drive.

        Args:
            query: Should contain 'file_id' or 'file_url' with Google Drive file identifier

        Returns:
            EpisodeMeta with downloaded file information
        """
        if not self.initialized:
            raise RuntimeError("Plugin not initialized")

        # Extract file ID from query
        file_id = query.get("file_id")
        if not file_id:
            # Try to extract from URL
            file_url = query.get("file_url", "")
            file_id = self._extract_file_id(file_url)

        if not file_id:
            raise ValueError("Google Drive file_id or file_url required in query")

        output_dir = Path(query.get("output_dir", "."))
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Get file metadata
            file_metadata = (
                self.service.files()
                .get(fileId=file_id, fields="id,name,size,createdTime,mimeType,webViewLink")
                .execute()
            )

            filename = file_metadata["name"]
            local_path = output_dir / filename

            logger.info(
                "Downloading from Google Drive",
                file_id=file_id,
                name=filename,
                size=file_metadata.get("size", "unknown"),
            )

            # Download the file
            request = self.service.files().get_media(fileId=file_id)
            with io.FileIO(str(local_path), "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.debug(f"Download progress: {int(status.progress() * 100)}%")

            # Extract episode info
            episode_title = query.get("title") or Path(filename).stem
            show_name = query.get("show") or "Google Drive Audio"

            # Create EpisodeMeta
            episode_meta = {
                "show": show_name,
                "episode_title": episode_title,
                "release_date": self._format_date(file_metadata.get("createdTime")),
                "description": query.get("description", ""),
                "duration": 0,  # Unknown until transcoded
                "audio_path": str(local_path),
                "episode_url": file_metadata.get("webViewLink", ""),
                "source": "google_drive",
                "metadata": {
                    "file_id": file_id,
                    "file_size": int(file_metadata.get("size", 0)),
                    "mime_type": file_metadata.get("mimeType"),
                    "created_time": file_metadata.get("createdTime"),
                },
            }

            logger.info(
                "File downloaded from Google Drive",
                title=episode_title,
                file=str(local_path),
            )

            return episode_meta

        except Exception as e:
            logger.error("Google Drive download failed", file_id=file_id, error=str(e))
            raise

    def supports_query(self, query: Dict[str, Any]) -> bool:
        """Check if this plugin can handle the given query."""
        # Check if it has a Google Drive file ID or URL
        file_id = query.get("file_id")
        file_url = query.get("file_url", "")

        return bool(file_id) or "drive.google.com" in file_url

    def list_folder(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List audio files in a Google Drive folder.

        Args:
            folder_id: Google Drive folder ID (None for root)

        Returns:
            List of file entries
        """
        if not self.initialized:
            raise RuntimeError("Plugin not initialized")

        try:
            # Build query for audio files
            query_parts = ["mimeType contains 'audio/'"]
            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")

            query = " and ".join(query_parts)

            results = (
                self.service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name, size, createdTime, mimeType, webViewLink)",
                    pageSize=100,
                )
                .execute()
            )

            files = results.get("files", [])
            entries = []

            for file in files:
                entries.append(
                    {
                        "id": file["id"],
                        "name": file["name"],
                        "size": int(file.get("size", 0)),
                        "created": file.get("createdTime"),
                        "mime_type": file.get("mimeType"),
                        "url": file.get("webViewLink"),
                    }
                )

            logger.info(f"Listed {len(entries)} audio files from Google Drive")
            return entries

        except Exception as e:
            logger.error("Failed to list Google Drive folder", error=str(e))
            raise

    def _authenticate(self) -> Credentials:
        """Authenticate with Google Drive API."""
        creds = None

        # Check for service account authentication
        if "service_account_file" in self.config:
            from google.oauth2 import service_account

            creds = service_account.Credentials.from_service_account_file(
                self.config["service_account_file"], scopes=SCOPES
            )
            logger.info("Using Google Drive service account authentication")
            return creds

        # Use OAuth authentication
        token_file = Path(self.config.get("token_file", "~/.podx/gdrive_token.json")).expanduser()

        # Load existing token if available
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if "credentials_file" not in self.config:
                    raise ValueError("credentials_file required for OAuth authentication")

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.config["credentials_file"], SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(creds.to_json())

        logger.info("Google Drive OAuth authentication successful")
        return creds

    def _extract_file_id(self, url: str) -> Optional[str]:
        """Extract file ID from Google Drive URL."""
        import re

        # Try different URL patterns
        patterns = [
            r"/file/d/([a-zA-Z0-9-_]+)",
            r"id=([a-zA-Z0-9-_]+)",
            r"/open\?id=([a-zA-Z0-9-_]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def _format_date(self, timestamp: Optional[str]) -> str:
        """Format ISO timestamp to standard date string."""
        if not timestamp:
            return datetime.now().strftime("%Y-%m-%d")

        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            return datetime.now().strftime("%Y-%m-%d")
