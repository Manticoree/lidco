"""WebhookServer — receive webhooks, verify signatures, dead-letter queue (stdlib only)."""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class WebhookEvent:
    id: str
    path: str
    payload: dict
    headers: dict
    timestamp: float
    result: Optional[Any] = None
    error: Optional[str] = None


class WebhookServer:
    """
    In-process webhook receiver.

    Parameters
    ----------
    secret:
        Default shared secret for HMAC-SHA256 signature verification.
    max_pending:
        Maximum events kept in the pending queue before oldest are evicted.
    """

    def __init__(self, secret: str = "", max_pending: int = 1000) -> None:
        self._secret = secret
        self._max_pending = max_pending
        self._endpoints: Dict[str, Callable[..., Any]] = {}
        self._pending: List[WebhookEvent] = []
        self._dead_letter: List[WebhookEvent] = []

    # -------------------------------------------------------- register

    def register_endpoint(self, path: str, handler: Callable[..., Any]) -> None:
        """Register *handler* for the given *path*."""
        if not path.startswith("/"):
            path = "/" + path
        self._endpoints[path] = handler

    # -------------------------------------------------------- verify

    @staticmethod
    def verify_signature(payload: str, signature: str, secret: str) -> bool:
        """Verify HMAC-SHA256 signature of *payload* against *secret*."""
        if not secret or not signature:
            return False
        expected = hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # -------------------------------------------------------- receive

    def receive(self, path: str, payload: dict, headers: Optional[dict] = None) -> dict:
        """
        Receive a webhook at *path* with *payload*.

        Returns a dict with ``status``, ``event_id``, and optionally ``result`` or ``error``.
        """
        headers = headers or {}
        if not path.startswith("/"):
            path = "/" + path

        event = WebhookEvent(
            id=uuid.uuid4().hex,
            path=path,
            payload=payload,
            headers=headers,
            timestamp=time.time(),
        )

        handler = self._endpoints.get(path)
        if handler is None:
            event.error = f"No handler for path: {path}"
            self._dead_letter.append(event)
            return {"status": "dead_letter", "event_id": event.id, "error": event.error}

        try:
            result = handler(payload, headers)
            event.result = result
            self._pending.append(event)
            if len(self._pending) > self._max_pending:
                self._pending = self._pending[-self._max_pending:]
            return {"status": "ok", "event_id": event.id, "result": result}
        except Exception as exc:
            event.error = str(exc)
            self._dead_letter.append(event)
            return {"status": "error", "event_id": event.id, "error": event.error}

    # -------------------------------------------------------- queries

    def pending_events(self) -> list:
        """Return list of successfully processed events."""
        return list(self._pending)

    def dead_letter(self) -> list:
        """Return list of events that failed or had no handler."""
        return list(self._dead_letter)

    def clear_pending(self) -> int:
        """Clear pending events, return count cleared."""
        count = len(self._pending)
        self._pending = []
        return count

    def clear_dead_letter(self) -> int:
        """Clear dead-letter queue, return count cleared."""
        count = len(self._dead_letter)
        self._dead_letter = []
        return count
