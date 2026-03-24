"""Webhook event bus — receive and dispatch events from GitHub/Slack/Linear (Cursor Automations parity)."""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class WebhookEvent:
    source: str        # "github" | "slack" | "linear" | "custom"
    event_type: str    # e.g. "push", "pull_request", "issue"
    payload: dict[str, Any]
    raw_body: str = ""
    signature: str = ""


@dataclass
class DispatchResult:
    event: WebhookEvent
    handlers_called: int
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


HandlerFn = Callable[[WebhookEvent], Awaitable[None]]


class WebhookEventBus:
    """Register handlers for webhook events and dispatch incoming payloads.

    Supports signature verification (HMAC-SHA256) for GitHub-style webhooks.
    """

    def __init__(self, secret: str = "") -> None:
        self._secret = secret
        self._handlers: dict[str, list[HandlerFn]] = {}   # event_type → handlers
        self._wildcard: list[HandlerFn] = []
        self._history: list[WebhookEvent] = []

    def on(self, event_type: str, handler: HandlerFn) -> None:
        """Register a handler for a specific event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    def on_any(self, handler: HandlerFn) -> None:
        """Register a handler for all events."""
        self._wildcard.append(handler)

    def verify_signature(self, body: str, signature: str) -> bool:
        """Verify GitHub-style HMAC-SHA256 signature."""
        if not self._secret:
            return True
        expected = "sha256=" + hmac.new(
            self._secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_github(self, body: str, event_header: str = "") -> WebhookEvent:
        """Parse a GitHub webhook payload."""
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}
        return WebhookEvent(
            source="github",
            event_type=event_header or payload.get("action", "unknown"),
            payload=payload,
            raw_body=body,
        )

    def parse_slack(self, body: str) -> WebhookEvent:
        """Parse a Slack event payload."""
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}
        event_type = payload.get("type", "unknown")
        if "event" in payload:
            event_type = payload["event"].get("type", event_type)
        return WebhookEvent(source="slack", event_type=event_type, payload=payload, raw_body=body)

    def parse_linear(self, body: str) -> WebhookEvent:
        """Parse a Linear webhook payload."""
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}
        event_type = payload.get("type", "unknown")
        return WebhookEvent(source="linear", event_type=event_type, payload=payload, raw_body=body)

    async def dispatch(self, event: WebhookEvent) -> DispatchResult:
        """Dispatch event to all matching handlers."""
        self._history.append(event)
        handlers = list(self._handlers.get(event.event_type, []))
        handlers += self._wildcard
        errors: list[str] = []
        called = 0
        for handler in handlers:
            try:
                await handler(event)
                called += 1
            except Exception as e:
                errors.append(str(e))
        return DispatchResult(event=event, handlers_called=called, errors=errors)

    def get_history(self, limit: int = 50) -> list[WebhookEvent]:
        return list(self._history[-limit:])

    def clear_history(self) -> None:
        self._history.clear()
