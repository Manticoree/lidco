"""Task notification system — Task 331.

Sends desktop or webhook notifications when long-running async tasks finish.

Usage::

    notifier = TaskNotifier()
    notifier.register_webhook("https://hooks.example.com/lidco", events=["done", "failed"])
    notifier.register_desktop(events=["done"])

    # Called when a task completes
    await notifier.notify(task_id="abc", event="done", message="Refactor complete")
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handler descriptors
# ---------------------------------------------------------------------------

@dataclass
class WebhookHandler:
    url: str
    events: list[str] = field(default_factory=lambda: ["done", "failed"])
    headers: dict[str, str] = field(default_factory=dict)
    timeout_s: float = 10.0


@dataclass
class DesktopHandler:
    events: list[str] = field(default_factory=lambda: ["done", "failed"])
    app_name: str = "LIDCO"


@dataclass
class NotificationEvent:
    task_id: str
    event: str   # done | failed | cancelled | started
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Notifier
# ---------------------------------------------------------------------------

class TaskNotifier:
    """Manages notification handlers for task lifecycle events.

    Supports desktop (system tray / toast) and HTTP webhook notifications.
    Handlers are fire-and-forget; failures are logged but not re-raised.
    """

    def __init__(self) -> None:
        self._webhooks: list[WebhookHandler] = []
        self._desktop: list[DesktopHandler] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_webhook(
        self,
        url: str,
        events: list[str] | None = None,
        headers: dict[str, str] | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        """Register an HTTP webhook to be called on task events."""
        self._webhooks.append(
            WebhookHandler(
                url=url,
                events=list(events or ["done", "failed"]),
                headers=dict(headers or {}),
                timeout_s=timeout_s,
            )
        )

    def register_desktop(
        self,
        events: list[str] | None = None,
        app_name: str = "LIDCO",
    ) -> None:
        """Register desktop notifications for task events."""
        self._desktop.append(
            DesktopHandler(
                events=list(events or ["done", "failed"]),
                app_name=app_name,
            )
        )

    def clear(self) -> None:
        """Remove all registered handlers."""
        self._webhooks.clear()
        self._desktop.clear()

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def notify(
        self,
        task_id: str,
        event: str,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Fire all matching handlers for the given event."""
        notification = NotificationEvent(
            task_id=task_id,
            event=event,
            message=message,
            metadata=metadata or {},
        )
        tasks = []
        for handler in self._webhooks:
            if event in handler.events:
                tasks.append(self._send_webhook(handler, notification))
        for handler in self._desktop:
            if event in handler.events:
                tasks.append(self._send_desktop(handler, notification))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_webhook(
        self, handler: WebhookHandler, notification: NotificationEvent
    ) -> None:
        payload = {
            "task_id": notification.task_id,
            "event": notification.event,
            "message": notification.message,
            "metadata": notification.metadata,
        }
        try:
            import httpx
            async with httpx.AsyncClient(timeout=handler.timeout_s) as client:
                resp = await client.post(
                    handler.url,
                    json=payload,
                    headers=handler.headers,
                )
                if resp.status_code >= 400:
                    logger.warning(
                        "Webhook %s returned HTTP %d", handler.url, resp.status_code
                    )
        except ImportError:
            logger.debug("httpx not installed — webhook notification skipped")
        except Exception as exc:
            logger.warning("Webhook notification failed: %s", exc)

    async def _send_desktop(
        self, handler: DesktopHandler, notification: NotificationEvent
    ) -> None:
        title = f"{handler.app_name}: Task {notification.event}"
        body = notification.message or f"Task {notification.task_id} {notification.event}"
        try:
            # Try plyer for cross-platform desktop notifications
            from plyer import notification as plyer_notif
            plyer_notif.notify(
                title=title,
                message=body,
                app_name=handler.app_name,
                timeout=5,
            )
        except ImportError:
            # Fallback: try win10toast on Windows
            try:
                import asyncio as _a
                import subprocess
                # Basic fallback: log the notification
                logger.info("Desktop notification [%s]: %s", title, body)
            except Exception:
                pass
        except Exception as exc:
            logger.warning("Desktop notification failed: %s", exc)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def webhook_count(self) -> int:
        return len(self._webhooks)

    @property
    def desktop_count(self) -> int:
        return len(self._desktop)
