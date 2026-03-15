"""Tests for TaskNotifier — Task 331."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.cloud.notifier import DesktopHandler, TaskNotifier, WebhookHandler


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestTaskNotifierRegistration:
    def test_register_webhook(self):
        notifier = TaskNotifier()
        notifier.register_webhook("https://example.com/hook")
        assert notifier.webhook_count == 1

    def test_register_desktop(self):
        notifier = TaskNotifier()
        notifier.register_desktop()
        assert notifier.desktop_count == 1

    def test_clear(self):
        notifier = TaskNotifier()
        notifier.register_webhook("https://x.com")
        notifier.register_desktop()
        notifier.clear()
        assert notifier.webhook_count == 0
        assert notifier.desktop_count == 0

    def test_default_events_webhook(self):
        notifier = TaskNotifier()
        notifier.register_webhook("https://x.com")
        handler = notifier._webhooks[0]
        assert "done" in handler.events
        assert "failed" in handler.events

    def test_custom_events_webhook(self):
        notifier = TaskNotifier()
        notifier.register_webhook("https://x.com", events=["done"])
        handler = notifier._webhooks[0]
        assert "done" in handler.events
        assert "failed" not in handler.events


# ---------------------------------------------------------------------------
# notify() — event filtering
# ---------------------------------------------------------------------------

class TestTaskNotifierNotify:
    def test_matching_event_fires_webhook(self):
        notifier = TaskNotifier()
        notifier.register_webhook("https://x.com", events=["done"])

        called_with = []
        async def fake_webhook(handler, notification):
            called_with.append(notification.event)
        notifier._send_webhook = fake_webhook

        asyncio.run(notifier.notify(task_id="abc", event="done", message="ok"))
        assert "done" in called_with

    def test_non_matching_event_skips_webhook(self):
        notifier = TaskNotifier()
        notifier.register_webhook("https://x.com", events=["done"])

        called_with = []
        async def fake_webhook(handler, notification):
            called_with.append(notification.event)
        notifier._send_webhook = fake_webhook

        asyncio.run(notifier.notify(task_id="abc", event="started", message="go"))
        assert len(called_with) == 0

    def test_multiple_webhooks_all_notified(self):
        notifier = TaskNotifier()
        notifier.register_webhook("https://a.com", events=["done"])
        notifier.register_webhook("https://b.com", events=["done"])

        call_count = []
        async def fake_webhook(handler, notification):
            call_count.append(1)
        notifier._send_webhook = fake_webhook

        asyncio.run(notifier.notify(task_id="x", event="done"))
        assert len(call_count) == 2

    def test_notify_no_handlers_noop(self):
        notifier = TaskNotifier()
        # Should not raise
        asyncio.run(notifier.notify(task_id="x", event="done"))


# ---------------------------------------------------------------------------
# WebhookHandler
# ---------------------------------------------------------------------------

class TestWebhookHandler:
    def test_defaults(self):
        h = WebhookHandler(url="https://x.com")
        assert h.timeout_s == 10.0
        assert h.headers == {}

    def test_custom_headers(self):
        h = WebhookHandler(url="https://x.com", headers={"X-Token": "secret"})
        assert h.headers["X-Token"] == "secret"
