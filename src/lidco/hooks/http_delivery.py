"""HTTP webhook delivery for hook events (Task 720)."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from lidco.hooks.event_bus import HookEvent


@dataclass
class HttpHookConfig:
    """Configuration for an HTTP webhook endpoint."""

    url: str
    method: str = "POST"
    headers: dict = field(default_factory=dict)
    timeout_s: float = 5.0
    retry_count: int = 2


@dataclass
class HttpDeliveryResult:
    """Result of an HTTP webhook delivery attempt."""

    status_code: int
    response_body: str
    success: bool
    error: str = ""


class HttpHookDelivery:
    """Delivers hook events as JSON payloads to an HTTP endpoint."""

    def __init__(
        self,
        config: HttpHookConfig,
        urlopen_fn: Callable | None = None,
    ) -> None:
        self._config = config
        self._urlopen_fn = urlopen_fn or urllib.request.urlopen

    def deliver(self, event: HookEvent) -> HttpDeliveryResult:
        """POST *event.payload* as JSON to the configured URL.

        Retries up to ``config.retry_count`` on exception.
        Returns :class:`HttpDeliveryResult` — never raises.
        """
        body = json.dumps(event.payload).encode("utf-8")
        headers = {**self._config.headers, "Content-Type": "application/json"}
        last_error = ""

        attempts = 1 + self._config.retry_count
        for attempt in range(attempts):
            try:
                req = urllib.request.Request(
                    self._config.url,
                    data=body,
                    headers=headers,
                    method=self._config.method,
                )
                resp = self._urlopen_fn(req, timeout=self._config.timeout_s)
                status_code = resp.status if hasattr(resp, "status") else resp.getcode()
                resp_body = resp.read().decode("utf-8") if hasattr(resp, "read") else ""
                return HttpDeliveryResult(
                    status_code=status_code,
                    response_body=resp_body,
                    success=200 <= status_code < 300,
                )
            except Exception as exc:
                last_error = str(exc)

        return HttpDeliveryResult(
            status_code=0,
            response_body="",
            success=False,
            error=last_error,
        )

    def as_hook_handler(self) -> Callable[[HookEvent], None]:
        """Return a callable ``(event) -> None`` that calls :meth:`deliver`."""

        def _handler(event: HookEvent) -> None:
            self.deliver(event)

        return _handler
