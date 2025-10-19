"""
Discord publish plugin for podx.

This plugin allows publishing transcripts and analysis results to Discord channels via webhooks.
"""

import json
from typing import Any, Dict, Union

from podx.logging import get_logger
from podx.plugins import PluginMetadata, PluginType, PublishPlugin
from podx.schemas import DeepcastBrief, Transcript

logger = get_logger(__name__)

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class DiscordPublishPlugin(PublishPlugin):
    """Publish plugin for sending content to Discord channels."""

    def __init__(self):
        self.initialized = False
        self.webhook_url = None
        self.username = "Podx Bot"
        self.avatar_url = None
        self.max_content_length = 2000  # Discord message limit

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="discord-publish",
            version="1.0.0",
            description="Publish transcripts and analysis to Discord channels",
            author="Podx Team",
            plugin_type=PluginType.PUBLISH,
            dependencies=["requests"],
            config_schema={
                "webhook_url": {
                    "type": "string",
                    "required": True,
                    "description": "Discord webhook URL",
                },
                "username": {
                    "type": "string",
                    "default": "Podx Bot",
                    "description": "Bot username for messages",
                },
                "avatar_url": {
                    "type": "string",
                    "description": "Bot avatar URL",
                },
                "format": {
                    "type": "string",
                    "default": "embed",
                    "enum": ["embed", "text", "file"],
                    "description": "Message format (embed, text, or file)",
                },
            },
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        if not REQUESTS_AVAILABLE:
            logger.error(
                "requests library not available. Install with: pip install requests"
            )
            return False

        if "webhook_url" not in config:
            logger.error("webhook_url is required in configuration")
            return False

        # Validate Discord webhook URL format
        url = config["webhook_url"]
        if not url.startswith("https://discord.com/api/webhooks/"):
            logger.error("Invalid Discord webhook URL format")
            return False

        return True

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library not available")

        self.webhook_url = config["webhook_url"]
        self.username = config.get("username", "Podx Bot")
        self.avatar_url = config.get("avatar_url")
        self.message_format = config.get("format", "embed")
        self.initialized = True

        logger.info("Discord publish plugin initialized")

    def publish_content(
        self, content: Union[Transcript, DeepcastBrief], **kwargs
    ) -> Dict[str, Any]:
        """
        Publish content to Discord channel.

        Args:
            content: Content to publish (Transcript or DeepcastBrief)
            **kwargs: Additional parameters (episode_meta, title, etc.)

        Returns:
            Dict with publishing results
        """
        if not self.initialized:
            raise RuntimeError("Plugin not initialized")

        # Determine content type
        is_transcript = isinstance(content, dict) and "segments" in content
        content_type = "transcript" if is_transcript else "analysis"

        # Prepare Discord message
        if self.message_format == "embed":
            payload = self._create_embed_message(content, content_type, kwargs)
        elif self.message_format == "text":
            payload = self._create_text_message(content, content_type, kwargs)
        else:  # file
            payload = self._create_file_message(content, content_type, kwargs)

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=30)
            response.raise_for_status()

            logger.info(
                "Content published to Discord",
                type=content_type,
                status_code=response.status_code,
            )

            return {
                "success": True,
                "status_code": response.status_code,
                "platform": "discord",
            }

        except requests.exceptions.RequestException as e:
            logger.error("Discord publish failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "platform": "discord",
            }

    def validate_credentials(self) -> bool:
        """Validate Discord webhook is active."""
        if not self.initialized:
            return False

        try:
            # Discord webhooks don't support ping, so send minimal test message
            payload = {
                "content": "✅ Podx webhook connection verified",
                "username": self.username,
            }

            if self.avatar_url:
                payload["avatar_url"] = self.avatar_url

            response = requests.post(self.webhook_url, json=payload, timeout=5)
            response.raise_for_status()

            logger.info("Discord webhook validated successfully")
            return True

        except requests.exceptions.RequestException as e:
            logger.error("Discord webhook validation failed", error=str(e))
            return False

    def _create_embed_message(
        self, content: Union[Transcript, DeepcastBrief], content_type: str, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create Discord embed message."""
        episode_meta = kwargs.get("episode_meta", {})
        title = kwargs.get("title", episode_meta.get("episode_title", "Podcast Processing Complete"))

        # Create embed
        embed = {
            "title": title,
            "type": "rich",
            "color": 0x5865F2,  # Discord blurple
        }

        # Add fields based on content type
        if content_type == "transcript":
            segments = content.get("segments", [])
            duration = content.get("duration", 0)

            embed["description"] = f"📝 Transcript generated with {len(segments)} segments"
            embed["fields"] = [
                {"name": "Duration", "value": f"{int(duration // 60)} minutes", "inline": True},
                {"name": "Segments", "value": str(len(segments)), "inline": True},
                {"name": "Model", "value": content.get("asr_model", "Unknown"), "inline": True},
            ]
        else:
            # Analysis/Deepcast
            brief_text = content.get("brief", "Analysis complete")
            if len(brief_text) > 300:
                brief_text = brief_text[:300] + "..."

            embed["description"] = brief_text

        # Add episode info if available
        if episode_meta:
            if "show" in episode_meta:
                embed["author"] = {"name": episode_meta["show"]}
            if "episode_url" in episode_meta:
                embed["url"] = episode_meta["episode_url"]

        payload = {
            "username": self.username,
            "embeds": [embed],
        }

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        return payload

    def _create_text_message(
        self, content: Union[Transcript, DeepcastBrief], content_type: str, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create Discord text message."""
        episode_meta = kwargs.get("episode_meta", {})
        title = kwargs.get("title", episode_meta.get("episode_title", "Podcast Processing"))

        # Build message text
        if content_type == "transcript":
            segments = content.get("segments", [])
            message = f"📝 **{title}**\n\nTranscript generated with {len(segments)} segments"
        else:
            brief = content.get("brief", "Analysis complete")
            if len(brief) > self.max_content_length - 100:
                brief = brief[: self.max_content_length - 100] + "..."
            message = f"🎙️ **{title}**\n\n{brief}"

        payload = {"content": message, "username": self.username}

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        return payload

    def _create_file_message(
        self, content: Union[Transcript, DeepcastBrief], content_type: str, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create Discord message with file attachment."""
        # For file uploads, we'd need to use multipart/form-data
        # This is a simplified version that sends a JSON code block instead

        episode_meta = kwargs.get("episode_meta", {})
        title = kwargs.get("title", episode_meta.get("episode_title", "Podcast Processing"))

        # Create JSON string
        content_json = json.dumps(content, indent=2)

        # Discord has a message limit, so truncate if needed
        if len(content_json) > self.max_content_length - 200:
            content_json = content_json[: self.max_content_length - 250] + "\n... (truncated)"

        message = f"📎 **{title}**\n\n```json\n{content_json}\n```"

        payload = {"content": message, "username": self.username}

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        return payload
