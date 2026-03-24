"""Tests for WebhookEventBus (T558)."""
from __future__ import annotations
import asyncio
import json
import pytest
from lidco.integrations.webhook_bus import WebhookEventBus, WebhookEvent


def test_parse_github():
    bus = WebhookEventBus()
    body = json.dumps({"action": "opened", "pull_request": {"title": "Fix bug"}})
    event = bus.parse_github(body, event_header="pull_request")
    assert event.source == "github"
    assert event.event_type == "pull_request"


def test_parse_slack():
    bus = WebhookEventBus()
    body = json.dumps({"type": "event_callback", "event": {"type": "message"}})
    event = bus.parse_slack(body)
    assert event.source == "slack"
    assert event.event_type == "message"


def test_parse_linear():
    bus = WebhookEventBus()
    body = json.dumps({"type": "Issue", "action": "create"})
    event = bus.parse_linear(body)
    assert event.source == "linear"
    assert event.event_type == "Issue"


def test_dispatch_calls_handler():
    bus = WebhookEventBus()
    called = []

    async def handler(event):
        called.append(event.event_type)

    bus.on("push", handler)
    event = WebhookEvent(source="github", event_type="push", payload={})
    result = asyncio.run(bus.dispatch(event))
    assert result.handlers_called == 1
    assert called == ["push"]


def test_dispatch_wildcard():
    bus = WebhookEventBus()
    received = []

    async def handler(event):
        received.append(event.source)

    bus.on_any(handler)
    event = WebhookEvent(source="slack", event_type="msg", payload={})
    asyncio.run(bus.dispatch(event))
    assert received == ["slack"]


def test_history_recorded():
    bus = WebhookEventBus()
    event = WebhookEvent(source="github", event_type="push", payload={})
    asyncio.run(bus.dispatch(event))
    assert len(bus.get_history()) == 1


def test_verify_signature_no_secret():
    bus = WebhookEventBus()
    assert bus.verify_signature("body", "any_sig") is True


def test_verify_signature_with_secret():
    import hashlib, hmac
    secret = "mysecret"
    body = '{"key":"value"}'
    sig = "sha256=" + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    bus = WebhookEventBus(secret=secret)
    assert bus.verify_signature(body, sig) is True
    assert bus.verify_signature(body, "sha256=wrong") is False
