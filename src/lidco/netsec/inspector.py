"""Request inspector — inspect, log, and block outbound HTTP requests (Q263)."""
from __future__ import annotations

import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass(frozen=True)
class InspectedRequest:
    """Record of an inspected outbound request."""

    id: str
    url: str
    method: str
    host: str
    timestamp: float
    blocked: bool = False
    reason: str = ""


class RequestInspector:
    """Inspect outbound HTTP requests; log; block unauthorized hosts."""

    def __init__(self, blocked_hosts: list[str] | None = None) -> None:
        self._blocked: list[str] = list(blocked_hosts) if blocked_hosts else []
        self._history: deque[InspectedRequest] = deque(maxlen=10000)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inspect(self, url: str, method: str = "GET") -> InspectedRequest:
        """Parse *url*, check against blocked list, log and return result."""
        parsed = urlparse(url)
        host = parsed.hostname or ""
        blocked = self.is_blocked(host)
        reason = f"host '{host}' matches blocked pattern" if blocked else ""
        req = InspectedRequest(
            id=uuid.uuid4().hex[:12],
            url=url,
            method=method.upper(),
            host=host,
            timestamp=time.time(),
            blocked=blocked,
            reason=reason,
        )
        self._history.append(req)
        return req

    def add_blocked(self, host_pattern: str) -> None:
        """Add a hostname pattern to the block list."""
        if host_pattern not in self._blocked:
            self._blocked.append(host_pattern)

    def remove_blocked(self, host_pattern: str) -> bool:
        """Remove a hostname pattern. Returns True if it existed."""
        try:
            self._blocked.remove(host_pattern)
            return True
        except ValueError:
            return False

    def is_blocked(self, host: str) -> bool:
        """Check *host* against blocked patterns (substring or glob ``*``)."""
        for pattern in self._blocked:
            if "*" in pattern:
                regex = re.escape(pattern).replace(r"\*", ".*")
                if re.fullmatch(regex, host):
                    return True
            else:
                if pattern in host:
                    return True
        return False

    def history(self, limit: int = 100) -> list[InspectedRequest]:
        """Return most recent inspected requests."""
        items = list(self._history)
        return items[-limit:]

    def blocked_requests(self) -> list[InspectedRequest]:
        """Return all blocked requests from history."""
        return [r for r in self._history if r.blocked]

    def clear_history(self) -> int:
        """Clear history and return the number of removed entries."""
        count = len(self._history)
        self._history.clear()
        return count

    def summary(self) -> dict:
        """Return summary statistics."""
        hosts = {r.host for r in self._history}
        blocked_count = sum(1 for r in self._history if r.blocked)
        return {
            "total": len(self._history),
            "blocked_count": blocked_count,
            "unique_hosts": len(hosts),
        }
