"""
Slack publishing plugin for podx.

This plugin publishes podcast analysis and summaries to Slack channels.
"""

import os
from typing import Any, Dict, Union

from podx.logging import get_logger
from podx.plugins import PluginMetadata, PluginType, PublishPlugin
from podx.schemas import DeepcastBrief, Transcript

logger = get_logger(__name__)

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False


class SlackPublishPlugin(PublishPlugin):
    """Publishing plugin for Slack integration."""

    def __init__(self):
        self.client = None
        self.initialized = False

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="slack-publish",
            version="1.0.0",
            description="Publish podcast summaries and analysis to Slack channels",
            author="Podx Team",
            plugin_type=PluginType.PUBLISH,
            dependencies=["slack-sdk"],
            config_schema={
                "bot_token": {"type": "string", "required": True},
                "default_channel": {"type": "string", "default": "#general"},
                "include_metadata": {"type": "boolean", "default": True},
                "max_message_length": {"type": "integer", "default": 3000},
            },
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        if not SLACK_AVAILABLE:
            logger.error(
                "slack-sdk library not available. Install with: pip install slack-sdk"
            )
            return False

        bot_token = config.get("bot_token") or os.getenv("SLACK_BOT_TOKEN")
        if not bot_token:
            logger.error(
                "Slack bot token not provided. Set SLACK_BOT_TOKEN environment variable"
            )
            return False

        return True

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        if not SLACK_AVAILABLE:
            raise ImportError("slack-sdk library not available")

        bot_token = config.get("bot_token") or os.getenv("SLACK_BOT_TOKEN")
        self.client = WebClient(token=bot_token)
        self.config = config
        self.initialized = True

        logger.info("Slack publish plugin initialized")

    def publish_content(
        self, content: Union[Transcript, DeepcastBrief], **kwargs
    ) -> Dict[str, Any]:
        """
        Publish content to Slack.

        Args:
            content: Content to publish (Transcript or DeepcastBrief)
            **kwargs: Publishing parameters (channel, thread_ts, etc.)

        Returns:
            Dict with publishing results
        """
        if not self.initialized:
            raise RuntimeError("Plugin not initialized")

        channel = kwargs.get("channel", self.config.get("default_channel", "#general"))
        thread_ts = kwargs.get("thread_ts")

        try:
            if isinstance(content, dict) and "markdown" in content:
                # DeepcastBrief format
                return self._publish_analysis(content, channel, thread_ts)
            else:
                # Transcript format
                return self._publish_transcript(content, channel, thread_ts)

        except SlackApiError as e:
            logger.error("Slack API error", error=str(e), channel=channel)
            raise
        except Exception as e:
            logger.error("Slack publish failed", error=str(e), channel=channel)
            raise

    def validate_credentials(self) -> bool:
        """Validate Slack credentials and permissions."""
        if not self.initialized:
            return False

        try:
            response = self.client.auth_test()
            logger.info(
                "Slack credentials validated",
                user=response["user"],
                team=response["team"],
            )
            return True
        except SlackApiError as e:
            logger.error("Slack credential validation failed", error=str(e))
            return False

    def _publish_analysis(
        self, analysis: DeepcastBrief, channel: str, thread_ts: str = None
    ) -> Dict[str, Any]:
        """Publish DeepcastBrief analysis to Slack."""
        # Extract metadata
        show = analysis.get("metadata", {}).get("show", "Unknown Show")
        episode = analysis.get("metadata", {}).get("episode_title", "Unknown Episode")

        # Create main message
        main_text = f"🎙️ *Podcast Analysis: {show}*\n📺 _{episode}_"

        # Send main message
        response = self.client.chat_postMessage(
            channel=channel, text=main_text, thread_ts=thread_ts
        )

        results = {
            "channel": channel,
            "message_ts": response["ts"],
            "thread_ts": response["ts"],
        }

        # Send summary in thread
        summary = analysis.get("summary", "")
        if summary:
            summary_text = f"📋 *Executive Summary*\n{summary}"
            self._send_threaded_message(channel, summary_text, response["ts"])

        # Send key points
        key_points = analysis.get("key_points", [])
        if key_points:
            points_text = "🎯 *Key Insights*\n" + "\n".join(
                [f"• {point}" for point in key_points[:8]]
            )
            self._send_threaded_message(channel, points_text, response["ts"])

        # Send quotes if available
        quotes = analysis.get("quotes", [])
        if quotes:
            quote_text = "💬 *Notable Quotes*\n"
            for quote in quotes[:3]:
                if isinstance(quote, dict):
                    speaker = quote.get("speaker", "Speaker")
                    text = quote.get("quote", quote.get("text", ""))
                    quote_text += f'>{speaker}: "{text}"\n'
                else:
                    quote_text += f'>"{quote}"\n'
            self._send_threaded_message(channel, quote_text, response["ts"])

        # Send metadata if enabled
        if self.config.get("include_metadata", True):
            metadata = analysis.get("metadata", {})
            if metadata:
                meta_text = "ℹ️ *Analysis Info*\n"
                model = metadata.get("model", "Unknown")
                provider = metadata.get("provider", "Unknown")
                meta_text += f"Model: {model} ({provider})"
                self._send_threaded_message(channel, meta_text, response["ts"])

        logger.info(
            "Analysis published to Slack",
            channel=channel,
            message_ts=response["ts"],
            show=show,
            episode=episode,
        )

        return results

    def _publish_transcript(
        self, transcript: Transcript, channel: str, thread_ts: str = None
    ) -> Dict[str, Any]:
        """Publish Transcript to Slack."""
        # Extract metadata
        show = transcript.get("show", "Unknown Show")
        episode = transcript.get("episode_title", "Unknown Episode")

        # Create summary message
        segments = transcript.get("segments", [])
        duration = transcript.get("duration", 0)
        segment_count = len(segments)

        main_text = f"🎙️ *Transcript Ready: {show}*\n📺 _{episode}_\n"
        main_text += f"⏱️ Duration: {duration//60}:{duration%60:02d}\n"
        main_text += f"📝 Segments: {segment_count}"

        # Send main message
        response = self.client.chat_postMessage(
            channel=channel, text=main_text, thread_ts=thread_ts
        )

        # Send first few segments as preview
        if segments:
            preview_text = "📄 *Transcript Preview*\n"
            preview_segments = segments[:3]

            for segment in preview_segments:
                text = segment.get("text", "").strip()
                if text:
                    speaker = segment.get("speaker", "")
                    if speaker:
                        preview_text += f"*{speaker}:* {text}\n"
                    else:
                        preview_text += f"{text}\n"

            if len(segments) > 3:
                preview_text += f"\n_...and {len(segments) - 3} more segments_"

            self._send_threaded_message(channel, preview_text, response["ts"])

        results = {
            "channel": channel,
            "message_ts": response["ts"],
            "thread_ts": response["ts"],
        }

        logger.info(
            "Transcript published to Slack",
            channel=channel,
            message_ts=response["ts"],
            show=show,
            episode=episode,
            segments=segment_count,
        )

        return results

    def _send_threaded_message(self, channel: str, text: str, thread_ts: str) -> None:
        """Send a message in a thread, splitting if too long."""
        max_length = self.config.get("max_message_length", 3000)

        if len(text) <= max_length:
            self.client.chat_postMessage(
                channel=channel, text=text, thread_ts=thread_ts
            )
        else:
            # Split long messages
            chunks = [text[i : i + max_length] for i in range(0, len(text), max_length)]
            for i, chunk in enumerate(chunks):
                if i > 0:
                    chunk = f"_(continued {i+1}/{len(chunks)})_\n" + chunk

                self.client.chat_postMessage(
                    channel=channel, text=chunk, thread_ts=thread_ts
                )
