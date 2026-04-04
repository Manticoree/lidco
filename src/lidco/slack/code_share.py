"""CodeShare — share code snippets to Slack channels (stdlib only)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from lidco.slack.client import SlackClient


@dataclass(frozen=True)
class SharedSnippet:
    """Metadata for a shared code snippet."""
    snippet_id: str
    channel: str
    language: str
    length: int
    timestamp: float


class CodeShare:
    """Share code snippets and files to Slack channels.

    Parameters
    ----------
    client:
        A :class:`SlackClient` used for delivery.
    """

    def __init__(self, client: SlackClient | None = None) -> None:
        self._client = client or SlackClient()
        self._snippets: list[SharedSnippet] = []
        self._threads: dict[str, list[dict]] = {}  # thread_id -> attachments

    # ------------------------------------------------------------ share

    def share(self, code: str, language: str, channel: str) -> dict:
        """Share a code snippet to *channel*.

        Returns a dict with ``ok``, ``snippet_id``, ``channel``, ``language``.
        """
        if not code:
            raise ValueError("code must not be empty")
        if not channel:
            raise ValueError("channel must not be empty")
        language = language or "text"
        formatted = f"```{language}\n{code}\n```"
        result = self._client.send_message(channel, formatted)
        snippet_id = uuid.uuid4().hex[:12]
        snippet = SharedSnippet(
            snippet_id=snippet_id,
            channel=channel,
            language=language,
            length=len(code),
            timestamp=time.time(),
        )
        self._snippets = [*self._snippets, snippet]
        return {
            "ok": True,
            "snippet_id": snippet_id,
            "channel": channel,
            "language": language,
            "ts": result.get("ts", ""),
        }

    # ----------------------------------------------------------- threads

    def create_thread(self, channel: str, title: str) -> str:
        """Create a discussion thread and return its thread_id."""
        if not channel:
            raise ValueError("channel must not be empty")
        if not title:
            raise ValueError("title must not be empty")
        result = self._client.send_message(channel, f"*Thread:* {title}")
        thread_id = result.get("ts", uuid.uuid4().hex[:12])
        self._threads = {**self._threads, thread_id: []}
        return thread_id

    def attach_file(self, thread: str, content: str, name: str) -> dict:
        """Attach a file to an existing thread.  Returns file metadata."""
        if not thread:
            raise ValueError("thread must not be empty")
        if not name:
            raise ValueError("name must not be empty")
        # Determine channel from thread context or use a default
        channel = "general"
        file_result = self._client.upload_file(channel, content, name)
        entry = {**file_result, "thread": thread, "name": name}
        attachments = self._threads.get(thread, [])
        self._threads = {**self._threads, thread: [*attachments, entry]}
        return entry

    # ----------------------------------------------------------- history

    def list_snippets(self) -> list[SharedSnippet]:
        """Return all shared snippets."""
        return list(self._snippets)
