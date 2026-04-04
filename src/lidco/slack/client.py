"""SlackClient — simulated Slack Web API (stdlib only)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RateLimitInfo:
    """Snapshot of rate-limit state."""
    calls_made: int
    window_start: float
    max_calls: int
    remaining: int


class SlackClient:
    """Simulated Slack Web API client.

    Parameters
    ----------
    token:
        Bot token (stored but not validated in simulation).
    rate_limit:
        Maximum API calls per *window_seconds*.  Default 50.
    window_seconds:
        Sliding-window duration for rate limiting.  Default 60.
    """

    def __init__(
        self,
        token: str = "",
        rate_limit: int = 50,
        window_seconds: float = 60.0,
    ) -> None:
        if not isinstance(token, str):
            raise TypeError("token must be a string")
        self._token = token
        self._rate_limit = rate_limit
        self._window_seconds = window_seconds

        # internal stores
        self._messages: dict[str, list[dict]] = {}  # channel -> messages
        self._channels: list[dict] = [
            {"id": "C001", "name": "general"},
            {"id": "C002", "name": "random"},
            {"id": "C003", "name": "dev"},
        ]
        self._files: list[dict] = []
        self._call_timestamps: list[float] = []

    # ---------------------------------------------------------------- helpers

    def _track_call(self) -> None:
        now = time.time()
        cutoff = now - self._window_seconds
        self._call_timestamps = [t for t in self._call_timestamps if t > cutoff]
        if len(self._call_timestamps) >= self._rate_limit:
            raise RuntimeError("Rate limit exceeded")
        self._call_timestamps = [*self._call_timestamps, now]

    def rate_limit_info(self) -> RateLimitInfo:
        """Return current rate-limit state."""
        now = time.time()
        cutoff = now - self._window_seconds
        recent = [t for t in self._call_timestamps if t > cutoff]
        return RateLimitInfo(
            calls_made=len(recent),
            window_start=cutoff,
            max_calls=self._rate_limit,
            remaining=max(0, self._rate_limit - len(recent)),
        )

    # ---------------------------------------------------------------- API

    def send_message(self, channel: str, text: str) -> dict:
        """Post a message to *channel*.  Returns message metadata dict."""
        if not channel:
            raise ValueError("channel must not be empty")
        if not text:
            raise ValueError("text must not be empty")
        self._track_call()
        ts = str(time.time())
        msg = {
            "ok": True,
            "channel": channel,
            "ts": ts,
            "text": text,
            "message_id": uuid.uuid4().hex[:12],
        }
        if channel not in self._messages:
            self._messages = {**self._messages, channel: []}
        self._messages[channel] = [*self._messages[channel], msg]
        return msg

    def list_channels(self) -> list[dict]:
        """Return the list of available channels."""
        self._track_call()
        return list(self._channels)

    def get_thread(self, channel: str, ts: str) -> list[dict]:
        """Return messages in *channel* matching thread timestamp *ts*."""
        if not channel:
            raise ValueError("channel must not be empty")
        self._track_call()
        msgs = self._messages.get(channel, [])
        return [m for m in msgs if m.get("ts") == ts or m.get("thread_ts") == ts]

    def upload_file(self, channel: str, content: str, filename: str) -> dict:
        """Upload a file to *channel*.  Returns file metadata dict."""
        if not channel:
            raise ValueError("channel must not be empty")
        if not filename:
            raise ValueError("filename must not be empty")
        self._track_call()
        file_id = uuid.uuid4().hex[:12]
        entry = {
            "ok": True,
            "file_id": file_id,
            "channel": channel,
            "filename": filename,
            "size": len(content),
        }
        self._files = [*self._files, entry]
        return entry
