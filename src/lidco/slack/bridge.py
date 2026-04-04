"""NotificationBridge — route notifications to Slack channels (stdlib only)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from lidco.slack.client import SlackClient


@dataclass(frozen=True)
class PendingNotification:
    """A notification queued but not yet delivered."""
    event_type: str
    message: str
    timestamp: float


class NotificationBridge:
    """Bridge between internal events and Slack channels.

    Parameters
    ----------
    client:
        A :class:`SlackClient` used for delivery.
    default_channel:
        Fallback channel when no mapping exists.  Default ``"general"``.
    """

    def __init__(
        self,
        client: SlackClient | None = None,
        default_channel: str = "general",
    ) -> None:
        self._client = client or SlackClient()
        self._default_channel = default_channel
        self._channel_map: dict[str, str] = {}  # event_type -> channel
        self._pending: list[PendingNotification] = []

    # ------------------------------------------------------------ config

    def configure_channel(self, event_type: str, channel: str) -> None:
        """Map *event_type* to a Slack *channel*."""
        if not event_type:
            raise ValueError("event_type must not be empty")
        if not channel:
            raise ValueError("channel must not be empty")
        self._channel_map = {**self._channel_map, event_type: channel}

    def get_channel(self, event_type: str) -> str:
        """Return the mapped channel for *event_type*, or the default."""
        return self._channel_map.get(event_type, self._default_channel)

    # ------------------------------------------------------------ notify

    def notify(self, event_type: str, message: str) -> bool:
        """Send a notification for *event_type*.  Returns True on success."""
        if not event_type:
            raise ValueError("event_type must not be empty")
        if not message:
            raise ValueError("message must not be empty")
        channel = self.get_channel(event_type)
        formatted = self.format_rich({"event_type": event_type, "message": message})
        try:
            self._client.send_message(channel, formatted)
            return True
        except Exception:
            self._pending = [
                *self._pending,
                PendingNotification(
                    event_type=event_type,
                    message=message,
                    timestamp=time.time(),
                ),
            ]
            return False

    # ----------------------------------------------------------- format

    @staticmethod
    def format_rich(data: dict) -> str:
        """Format a dict into a rich Slack message string."""
        event = data.get("event_type", "unknown")
        message = data.get("message", "")
        return f"[{event.upper()}] {message}"

    # ----------------------------------------------------------- pending

    def pending(self) -> list[PendingNotification]:
        """Return a copy of pending (failed) notifications."""
        return list(self._pending)

    def clear_pending(self) -> int:
        """Clear pending queue, return count removed."""
        count = len(self._pending)
        self._pending = []
        return count
