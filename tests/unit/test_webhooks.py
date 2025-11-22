"""Tests for webhook notification system."""

import hashlib
import hmac
from unittest.mock import Mock, patch

import httpx
import pytest

from podx.webhooks import WebhookClient, WebhookError, WebhookEvent, WebhookManager


class TestWebhookClient:
    """Test WebhookClient."""

    def test_init(self):
        """Test client initialization."""
        client = WebhookClient(
            webhook_url="https://example.com/webhook",
            secret="test-secret",
            timeout=5.0,
            max_retries=2,
        )

        assert client.webhook_url == "https://example.com/webhook"
        assert client.secret == "test-secret"
        assert client.timeout == 5.0
        assert client.max_retries == 2

    def test_generate_signature(self):
        """Test HMAC signature generation."""
        client = WebhookClient(
            webhook_url="https://example.com/webhook",
            secret="test-secret",
        )

        payload = '{"event":"job.started","data":{}}'
        signature = client._generate_signature(payload)

        # Verify signature
        expected = hmac.new(
            b"test-secret",
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert signature == expected

    def test_generate_signature_no_secret(self):
        """Test signature generation without secret."""
        client = WebhookClient(webhook_url="https://example.com/webhook")
        signature = client._generate_signature("test")
        assert signature == ""

    @patch("httpx.post")
    def test_send_success(self, mock_post):
        """Test successful webhook delivery."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        client = WebhookClient(webhook_url="https://example.com/webhook")
        result = client.send(WebhookEvent.JOB_STARTED, job_id="test-123")

        assert result is True
        assert mock_post.call_count == 1

    @patch("httpx.post")
    def test_send_with_signature(self, mock_post):
        """Test webhook delivery with HMAC signature."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        client = WebhookClient(
            webhook_url="https://example.com/webhook",
            secret="test-secret",
        )

        client.send(WebhookEvent.JOB_STARTED)

        # Verify signature header was added
        call_kwargs = mock_post.call_args.kwargs
        assert "X-Webhook-Signature" in call_kwargs["headers"]

    @patch("httpx.post")
    def test_send_retry_on_failure(self, mock_post):
        """Test retry logic on transient failures."""
        # First two attempts fail, third succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 503
        mock_response_fail.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Service Unavailable",
                request=Mock(),
                response=mock_response_fail,
            )
        )

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.raise_for_status = Mock()

        mock_post.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success,
        ]

        client = WebhookClient(
            webhook_url="https://example.com/webhook",
            max_retries=3,
            retry_delay=0.01,  # Short delay for testing
        )

        result = client.send(WebhookEvent.JOB_COMPLETED)

        assert result is True
        assert mock_post.call_count == 3

    @patch("httpx.post")
    def test_send_failure_exhausted_retries(self, mock_post):
        """Test failure after exhausting retries."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error",
                request=Mock(),
                response=mock_response,
            )
        )

        mock_post.return_value = mock_response

        client = WebhookClient(
            webhook_url="https://example.com/webhook",
            max_retries=2,
            retry_delay=0.01,
        )

        with pytest.raises(WebhookError):
            client.send(WebhookEvent.JOB_FAILED)

        assert mock_post.call_count == 2


class TestWebhookManager:
    """Test WebhookManager."""

    def test_register(self):
        """Test webhook registration."""
        manager = WebhookManager()

        client = manager.register(
            webhook_url="https://example.com/webhook",
            secret="test-secret",
        )

        assert isinstance(client, WebhookClient)
        assert len(manager.clients) == 1
        assert manager.clients[0]["url"] == "https://example.com/webhook"

    def test_register_with_event_filter(self):
        """Test registration with event filtering."""
        manager = WebhookManager()

        events = {WebhookEvent.JOB_STARTED, WebhookEvent.JOB_COMPLETED}
        manager.register(
            webhook_url="https://example.com/webhook",
            events=events,
        )

        assert manager.clients[0]["events"] == events

    @patch("httpx.post")
    def test_notify_all_clients(self, mock_post):
        """Test notification to multiple clients."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        manager = WebhookManager()
        manager.register("https://example.com/webhook1")
        manager.register("https://example.com/webhook2")

        successful = manager.notify(
            WebhookEvent.JOB_STARTED,
            job_id="test-123",
            data={"status": "running"},
        )

        assert successful == 2
        assert mock_post.call_count == 2

    @patch("httpx.post")
    def test_notify_event_filtering(self, mock_post):
        """Test event filtering."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        manager = WebhookManager()

        # Client 1: All events
        manager.register("https://example.com/webhook1")

        # Client 2: Only job.started events
        manager.register(
            "https://example.com/webhook2",
            events={WebhookEvent.JOB_STARTED},
        )

        # Send job.completed event
        successful = manager.notify(WebhookEvent.JOB_COMPLETED)

        # Only client 1 should receive it
        assert successful == 1
        assert mock_post.call_count == 1

    @patch("httpx.post")
    def test_notify_no_raise_on_error(self, mock_post):
        """Test notification with raise_on_error=False."""
        # First client fails all retries (3 attempts), second succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Error",
                request=Mock(),
                response=mock_response_fail,
            )
        )

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.raise_for_status = Mock()

        # First webhook will retry 3 times (all fail), then second webhook succeeds
        mock_post.side_effect = [
            mock_response_fail,  # webhook1 attempt 1
            mock_response_fail,  # webhook1 attempt 2
            mock_response_fail,  # webhook1 attempt 3 (exhausted)
            mock_response_success,  # webhook2 attempt 1 (success)
        ]

        manager = WebhookManager()
        manager.register("https://example.com/webhook1", max_retries=3)
        manager.register("https://example.com/webhook2")

        # Should not raise, returns 1 successful
        successful = manager.notify(
            WebhookEvent.JOB_STARTED,
            raise_on_error=False,
        )

        assert successful == 1

    def test_clear(self):
        """Test clearing all webhooks."""
        manager = WebhookManager()
        manager.register("https://example.com/webhook1")
        manager.register("https://example.com/webhook2")

        assert len(manager.clients) == 2

        manager.clear()

        assert len(manager.clients) == 0

    def test_get_registered_urls(self):
        """Test getting registered URLs."""
        manager = WebhookManager()
        manager.register("https://example.com/webhook1")
        manager.register("https://example.com/webhook2")

        urls = manager.get_registered_urls()

        assert len(urls) == 2
        assert "https://example.com/webhook1" in urls
        assert "https://example.com/webhook2" in urls
