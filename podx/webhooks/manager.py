"""Webhook manager for pipeline integration."""

from typing import Any, Dict, List, Optional, Set

from podx.logging import get_logger

from .client import WebhookClient, WebhookError, WebhookEvent

logger = get_logger(__name__)


class WebhookManager:
    """Manages webhook clients and event distribution.

    Allows registering multiple webhook URLs with event filtering.
    """

    def __init__(self):
        """Initialize webhook manager."""
        self.clients: List[Dict[str, Any]] = []

    def register(
        self,
        webhook_url: str,
        secret: Optional[str] = None,
        events: Optional[Set[WebhookEvent]] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> WebhookClient:
        """Register a webhook endpoint.

        Args:
            webhook_url: Target URL for webhooks
            secret: Optional shared secret for HMAC signatures
            events: Optional set of events to subscribe to (None = all events)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts

        Returns:
            Configured WebhookClient instance
        """
        client = WebhookClient(
            webhook_url=webhook_url,
            secret=secret,
            timeout=timeout,
            max_retries=max_retries,
        )

        self.clients.append(
            {
                "client": client,
                "events": events,  # None means all events
                "url": webhook_url,
            }
        )

        logger.info(
            "Webhook registered",
            url=webhook_url,
            events=list(events) if events else "all",
        )

        return client

    def notify(
        self,
        event: WebhookEvent,
        job_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        raise_on_error: bool = False,
    ) -> int:
        """Send notification to all registered webhooks.

        Args:
            event: Event type
            job_id: Optional job identifier
            data: Optional event data
            raise_on_error: If True, raise exception on first failure

        Returns:
            Number of successful deliveries

        Raises:
            WebhookError: If raise_on_error=True and any delivery fails
        """
        if not self.clients:
            logger.debug("No webhooks registered, skipping notification")
            return 0

        successful = 0
        for client_config in self.clients:
            client = client_config["client"]
            subscribed_events = client_config["events"]

            # Check if client is subscribed to this event
            if subscribed_events is not None and event not in subscribed_events:
                logger.debug(
                    "Skipping webhook (not subscribed)",
                    url=client_config["url"],
                    event_type=event.value,
                )
                continue

            try:
                client.send(event=event, job_id=job_id, data=data)
                successful += 1

            except WebhookError as e:
                logger.error(
                    "Webhook delivery failed",
                    url=client_config["url"],
                    event_type=event.value,
                    error=str(e),
                )

                if raise_on_error:
                    raise

        logger.info(
            "Webhook notifications sent",
            event_type=event.value,
            successful=successful,
            total=len(self.clients),
        )

        return successful

    async def notify_async(
        self,
        event: WebhookEvent,
        job_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        raise_on_error: bool = False,
    ) -> int:
        """Send notification asynchronously to all registered webhooks.

        Args:
            event: Event type
            job_id: Optional job identifier
            data: Optional event data
            raise_on_error: If True, raise exception on first failure

        Returns:
            Number of successful deliveries

        Raises:
            WebhookError: If raise_on_error=True and any delivery fails
        """
        if not self.clients:
            logger.debug("No webhooks registered, skipping notification")
            return 0

        import asyncio

        tasks = []
        for client_config in self.clients:
            client = client_config["client"]
            subscribed_events = client_config["events"]

            # Check if client is subscribed to this event
            if subscribed_events is not None and event not in subscribed_events:
                logger.debug(
                    "Skipping webhook (not subscribed)",
                    url=client_config["url"],
                    event_type=event.value,
                )
                continue

            tasks.append(client.send_async(event=event, job_id=job_id, data=data))

        if not tasks:
            return 0

        # Execute all webhook deliveries concurrently
        results = await asyncio.gather(*tasks, return_exceptions=not raise_on_error)

        successful = sum(1 for r in results if r is True)

        logger.info(
            "Webhook notifications sent (async)",
            event_type=event.value,
            successful=successful,
            total=len(tasks),
        )

        return successful

    def clear(self):
        """Remove all registered webhooks."""
        count = len(self.clients)
        self.clients.clear()
        logger.info("Webhooks cleared", count=count)

    def get_registered_urls(self) -> List[str]:
        """Get list of registered webhook URLs.

        Returns:
            List of webhook URLs
        """
        return [c["url"] for c in self.clients]
