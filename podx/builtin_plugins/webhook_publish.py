"""
Webhook publish plugin for podx.

This plugin allows publishing transcripts and analysis results to custom webhooks.
"""

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


class WebhookPublishPlugin(PublishPlugin):
    """Publish plugin for sending content to webhooks."""

    def __init__(self):
        self.initialized = False
        self.webhook_url = None
        self.headers = {}
        self.timeout = 30

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="webhook-publish",
            version="1.0.0",
            description="Publish transcripts and analysis to custom webhooks",
            author="Podx Team",
            plugin_type=PluginType.PUBLISH,
            dependencies=["requests"],
            config_schema={
                "webhook_url": {
                    "type": "string",
                    "required": True,
                    "description": "Webhook URL to POST content to",
                },
                "headers": {
                    "type": "object",
                    "default": {},
                    "description": "Custom HTTP headers",
                },
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "description": "Request timeout in seconds",
                },
                "include_metadata": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include episode metadata in payload",
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

        # Validate URL format
        url = config["webhook_url"]
        if not url.startswith(("http://", "https://")):
            logger.error("webhook_url must start with http:// or https://")
            return False

        return True

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library not available")

        self.webhook_url = config["webhook_url"]
        self.headers = config.get("headers", {})
        self.timeout = config.get("timeout", 30)
        self.include_metadata = config.get("include_metadata", True)
        self.initialized = True

        logger.info("Webhook publish plugin initialized", url=self.webhook_url)

    def publish_content(
        self, content: Union[Transcript, DeepcastBrief], **kwargs
    ) -> Dict[str, Any]:
        """
        Publish content to webhook.

        Args:
            content: Content to publish (Transcript or DeepcastBrief)
            **kwargs: Additional parameters (episode_meta, etc.)

        Returns:
            Dict with publishing results
        """
        if not self.initialized:
            raise RuntimeError("Plugin not initialized")

        # Prepare payload
        payload = self._prepare_payload(content, kwargs)

        # Add custom headers
        headers = {
            "Content-Type": "application/json",
            **self.headers,
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )

            response.raise_for_status()

            logger.info(
                "Content published to webhook",
                url=self.webhook_url,
                status_code=response.status_code,
            )

            return {
                "success": True,
                "status_code": response.status_code,
                "response": response.text,
                "webhook_url": self.webhook_url,
            }

        except requests.exceptions.Timeout:
            logger.error("Webhook request timed out", url=self.webhook_url)
            return {
                "success": False,
                "error": "Request timed out",
                "webhook_url": self.webhook_url,
            }

        except requests.exceptions.RequestException as e:
            logger.error("Webhook request failed", url=self.webhook_url, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "webhook_url": self.webhook_url,
            }

    def validate_credentials(self) -> bool:
        """Validate webhook URL is reachable."""
        if not self.initialized:
            return False

        try:
            # Send a test ping with minimal payload
            response = requests.post(
                self.webhook_url,
                json={"type": "ping", "source": "podx-webhook-plugin"},
                headers={"Content-Type": "application/json", **self.headers},
                timeout=5,
            )

            # Accept 2xx, 4xx (webhook exists but rejected ping)
            # Don't accept 5xx (server error)
            if response.status_code < 500:
                logger.info(
                    "Webhook URL validated", url=self.webhook_url, status=response.status_code
                )
                return True

            logger.warning(
                "Webhook returned server error",
                url=self.webhook_url,
                status=response.status_code,
            )
            return False

        except requests.exceptions.RequestException as e:
            logger.error("Webhook validation failed", url=self.webhook_url, error=str(e))
            return False

    def _prepare_payload(
        self, content: Union[Transcript, DeepcastBrief], kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare webhook payload from content."""
        payload = {
            "source": "podx",
            "type": "transcript" if isinstance(content, dict) and "segments" in content else "analysis",
            "timestamp": kwargs.get("timestamp"),
        }

        # Add episode metadata if available
        if self.include_metadata and "episode_meta" in kwargs:
            payload["episode"] = kwargs["episode_meta"]

        # Add content
        if isinstance(content, dict):
            # Already a dict (from Pydantic model)
            payload["content"] = content
        else:
            # Convert Pydantic model to dict
            payload["content"] = content.model_dump() if hasattr(content, "model_dump") else content

        # Add custom fields from kwargs
        for key, value in kwargs.items():
            if key not in ["episode_meta", "timestamp"]:
                payload[key] = value

        return payload
