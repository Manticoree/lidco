"""NotificationCenter — multi-channel notification dispatch (stdlib only)."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable
from urllib.error import HTTPError, URLError

_VALID_LEVELS = frozenset({"info", "warning", "error", "success"})


@dataclass
class Notification:
    title: str
    body: str
    level: str  # "info" | "warning" | "error" | "success"
    timestamp: float = field(default_factory=time.time)
    channels: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class NotificationCenter:
    """
    Multi-channel notification dispatch (log, webhook, desktop).

    Parameters
    ----------
    max_history:
        Maximum notifications retained in history (oldest dropped).  Default 100.
    log_callback:
        Custom log function called for the ``"log"`` channel.  Default: ``print``.
    """

    def __init__(
        self,
        max_history: int = 100,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._max_history = max_history
        self._log_fn: Callable[[str], None] = log_callback or print
        self._history: list[Notification] = []
        self._webhooks: list[str] = []
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- webhooks

    def add_webhook(self, url: str) -> None:
        """Register a webhook URL for notifications."""
        with self._lock:
            if url not in self._webhooks:
                self._webhooks = [*self._webhooks, url]

    def remove_webhook(self, url: str) -> bool:
        """Unregister a webhook URL.  Returns *True* if it existed."""
        with self._lock:
            if url not in self._webhooks:
                return False
            self._webhooks = [u for u in self._webhooks if u != url]
            return True

    def list_webhooks(self) -> list[str]:
        """Return a copy of registered webhook URLs."""
        with self._lock:
            return list(self._webhooks)

    # -------------------------------------------------------------------- core

    def send(
        self,
        title: str,
        body: str,
        level: str = "info",
        channels: list[str] | None = None,
    ) -> Notification:
        """
        Dispatch a notification to the requested channels.

        Parameters
        ----------
        title:
            Short title.
        body:
            Notification body text.
        level:
            One of ``info``, ``warning``, ``error``, ``success``.
        channels:
            Explicit channel list.  *None* → ``["log"]`` plus ``"webhook"`` if
            any webhooks are registered.

        Raises
        ------
        ValueError
            If *level* is not one of the valid values.
        """
        if level not in _VALID_LEVELS:
            raise ValueError(f"Invalid level {level!r}. Must be one of {sorted(_VALID_LEVELS)}")

        n = Notification(title=title, body=body, level=level)

        if channels is None:
            channels = ["log"]
            with self._lock:
                has_webhooks = bool(self._webhooks)
            if has_webhooks:
                channels = [*channels, "webhook"]
        n.channels = list(channels)

        for ch in channels:
            if ch == "log":
                self._send_log(n)
            elif ch == "webhook":
                with self._lock:
                    urls = list(self._webhooks)
                for url in urls:
                    self._send_webhook(n, url)
            elif ch == "desktop":
                self._send_desktop(n)

        with self._lock:
            self._history = [*self._history, n]
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        return n

    # ----------------------------------------------------------------- history

    def get_history(self) -> list[Notification]:
        """Return notifications newest-first."""
        with self._lock:
            return list(reversed(self._history))

    def clear_history(self) -> int:
        """Clear history and return the number of entries removed."""
        with self._lock:
            count = len(self._history)
            self._history = []
            return count

    # ---------------------------------------------------------- private senders

    def _send_log(self, n: Notification) -> None:
        self._log_fn(f"[{n.level.upper()}] {n.title}: {n.body}")

    def _send_webhook(self, n: Notification, url: str) -> None:
        payload = json.dumps(
            {"title": n.title, "body": n.body, "level": n.level, "timestamp": n.timestamp}
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=10)
        except (URLError, HTTPError, OSError) as exc:
            n.errors.append(f"webhook {url}: {exc}")

    def _send_desktop(self, n: Notification) -> None:
        title = n.title
        body = n.body
        try:
            if sys.platform.startswith("linux"):
                subprocess.run(["notify-send", title, body], timeout=5, check=False)
            elif sys.platform == "darwin":
                script = f'display notification "{body}" with title "{title}"'
                subprocess.run(["osascript", "-e", script], timeout=5, check=False)
            elif sys.platform == "win32":
                subprocess.run(["msg", "*", f"{title}: {body}"], timeout=5, check=False)
        except Exception as exc:  # noqa: BLE001
            n.errors.append(f"desktop: {exc}")
