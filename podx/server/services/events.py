"""Event broadcasting system for real-time progress updates.

Provides an in-memory pub/sub system for streaming job progress events via SSE.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional

from podx.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProgressEvent:
    """Progress event for a job."""

    job_id: str
    percentage: Optional[float] = None
    message: Optional[str] = None
    step: Optional[str] = None
    status: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class EventBroadcaster:
    """In-memory event broadcaster for job progress updates.

    Allows multiple SSE clients to subscribe to job updates and receive
    real-time progress events without polling the database.
    """

    def __init__(self):
        """Initialize the event broadcaster."""
        # Map of job_id -> list of queues for subscribers
        self._subscribers: Dict[str, list[asyncio.Queue[ProgressEvent]]] = defaultdict(
            list
        )
        self._lock = asyncio.Lock()

    async def subscribe(self, job_id: str) -> AsyncIterator[ProgressEvent]:
        """Subscribe to progress events for a job.

        Args:
            job_id: Job ID to subscribe to

        Yields:
            Progress events as they occur
        """
        queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()

        # Add subscriber
        async with self._lock:
            self._subscribers[job_id].append(queue)
            logger.debug(
                f"Client subscribed to job {job_id} ({len(self._subscribers[job_id])} total subscribers)"
            )

        try:
            while True:
                # Wait for next event
                event = await queue.get()
                yield event

                # If job is complete, stop subscribing
                if event.status in ("completed", "failed", "cancelled"):
                    break

        finally:
            # Remove subscriber
            async with self._lock:
                if queue in self._subscribers[job_id]:
                    self._subscribers[job_id].remove(queue)
                    logger.debug(
                        f"Client unsubscribed from job {job_id} ({len(self._subscribers[job_id])} remaining)"
                    )

                # Clean up if no more subscribers
                if not self._subscribers[job_id]:
                    del self._subscribers[job_id]
                    logger.debug(f"No more subscribers for job {job_id}, cleaned up")

    async def publish(self, event: ProgressEvent) -> None:
        """Publish a progress event to all subscribers.

        Args:
            event: Progress event to publish
        """
        async with self._lock:
            subscribers = self._subscribers.get(event.job_id, [])

            if not subscribers:
                logger.debug(
                    f"No subscribers for job {event.job_id}, event not broadcasted"
                )
                return

            logger.debug(
                f"Broadcasting event to {len(subscribers)} subscribers for job {event.job_id}"
            )

            # Send event to all subscribers
            for queue in subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(
                        f"Subscriber queue full for job {event.job_id}, dropping event"
                    )

    def has_subscribers(self, job_id: str) -> bool:
        """Check if a job has any active subscribers.

        Args:
            job_id: Job ID to check

        Returns:
            True if job has subscribers, False otherwise
        """
        return bool(self._subscribers.get(job_id))

    def get_subscriber_count(self, job_id: str) -> int:
        """Get the number of subscribers for a job.

        Args:
            job_id: Job ID to check

        Returns:
            Number of active subscribers
        """
        return len(self._subscribers.get(job_id, []))


# Global broadcaster instance
_broadcaster: Optional[EventBroadcaster] = None


def get_broadcaster() -> EventBroadcaster:
    """Get the global event broadcaster instance.

    Returns:
        Global EventBroadcaster instance
    """
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster()
    return _broadcaster
