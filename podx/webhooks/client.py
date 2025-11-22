"""Webhook HTTP client with retry logic and security."""

import hashlib
import hmac
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel, Field

from podx.logging import get_logger

logger = get_logger(__name__)


class WebhookEvent(str, Enum):
    """Webhook event types."""

    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"


class WebhookPayload(BaseModel):
    """Webhook payload structure."""

    event: WebhookEvent
    timestamp: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat()
    )
    job_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class WebhookError(Exception):
    """Raised when webhook delivery fails."""

    pass


class WebhookClient:
    """HTTP client for delivering webhook notifications.

    Features:
    - Exponential backoff retry logic
    - HMAC signature verification
    - Timeout handling
    - Async support
    """

    def __init__(
        self,
        webhook_url: str,
        secret: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize webhook client.

        Args:
            webhook_url: Target URL for webhook delivery
            secret: Optional shared secret for HMAC signatures
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.webhook_url = webhook_url
        self.secret = secret
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for payload.

        Args:
            payload: JSON payload string

        Returns:
            Hex-encoded HMAC signature
        """
        if not self.secret:
            return ""

        return hmac.new(
            self.secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def send(
        self,
        event: WebhookEvent,
        job_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send webhook notification with retry logic.

        Args:
            event: Event type
            job_id: Optional job identifier
            data: Optional event data

        Returns:
            True if delivery succeeded, False otherwise

        Raises:
            WebhookError: If all retry attempts fail
        """
        payload = WebhookPayload(
            event=event,
            job_id=job_id,
            data=data or {},
        )

        payload_json = payload.model_dump_json()

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "PodX-Webhook/3.0",
        }

        # Add HMAC signature if secret is configured
        if self.secret:
            signature = self._generate_signature(payload_json)
            headers["X-Webhook-Signature"] = signature

        # Retry with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = httpx.post(
                    self.webhook_url,
                    content=payload_json,
                    headers=headers,
                    timeout=self.timeout,
                )

                response.raise_for_status()

                logger.info(
                    "Webhook delivered",
                    event_type=event.value,
                    url=self.webhook_url,
                    status=response.status_code,
                    attempt=attempt + 1,
                )

                return True

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    "Webhook delivery failed",
                    event_type=event.value,
                    url=self.webhook_url,
                    status=e.response.status_code,
                    attempt=attempt + 1,
                    error=str(e),
                )

            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    "Webhook request error",
                    event_type=event.value,
                    url=self.webhook_url,
                    attempt=attempt + 1,
                    error=str(e),
                )

            # Exponential backoff
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2**attempt)
                logger.debug(f"Retrying in {delay}s...")
                time.sleep(delay)

        # All retries exhausted
        error_msg = f"Webhook delivery failed after {self.max_retries} attempts"
        logger.error(
            error_msg,
            event_type=event.value,
            url=self.webhook_url,
            last_error=str(last_error),
        )

        raise WebhookError(error_msg) from last_error

    async def send_async(
        self,
        event: WebhookEvent,
        job_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send webhook notification asynchronously.

        Args:
            event: Event type
            job_id: Optional job identifier
            data: Optional event data

        Returns:
            True if delivery succeeded, False otherwise

        Raises:
            WebhookError: If all retry attempts fail
        """
        payload = WebhookPayload(
            event=event,
            job_id=job_id,
            data=data or {},
        )

        payload_json = payload.model_dump_json()

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "PodX-Webhook/3.0",
        }

        if self.secret:
            signature = self._generate_signature(payload_json)
            headers["X-Webhook-Signature"] = signature

        last_error = None
        async with httpx.AsyncClient() as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.post(
                        self.webhook_url,
                        content=payload_json,
                        headers=headers,
                        timeout=self.timeout,
                    )

                    response.raise_for_status()

                    logger.info(
                        "Webhook delivered (async)",
                        event_type=event.value,
                        url=self.webhook_url,
                        status=response.status_code,
                        attempt=attempt + 1,
                    )

                    return True

                except httpx.HTTPStatusError as e:
                    last_error = e
                    logger.warning(
                        "Webhook delivery failed (async)",
                        event_type=event.value,
                        url=self.webhook_url,
                        status=e.response.status_code,
                        attempt=attempt + 1,
                        error=str(e),
                    )

                except httpx.RequestError as e:
                    last_error = e
                    logger.warning(
                        "Webhook request error (async)",
                        event_type=event.value,
                        url=self.webhook_url,
                        attempt=attempt + 1,
                        error=str(e),
                    )

                # Exponential backoff
                if attempt < self.max_retries - 1:
                    import asyncio

                    delay = self.retry_delay * (2**attempt)
                    logger.debug(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)

        error_msg = f"Webhook delivery failed after {self.max_retries} attempts"
        logger.error(
            error_msg,
            event_type=event.value,
            url=self.webhook_url,
            last_error=str(last_error),
        )

        raise WebhookError(error_msg) from last_error
