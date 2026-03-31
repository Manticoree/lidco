"""Simulated connection pool — stdlib only (no real sockets)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Connection:
    """A simulated network connection."""

    id: str = ""
    host: str = ""
    created_at: float = 0.0
    last_used: float = 0.0
    is_active: bool = False


class ConnectionPool:
    """Manage a pool of simulated connections with idle eviction."""

    def __init__(self, max_size: int = 10, max_idle_time: float = 60.0) -> None:
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self._connections: dict[str, Connection] = {}

    def acquire(self, host: str) -> Connection:
        """Get an idle connection for *host*, or create one.

        Raises ``RuntimeError`` if the pool is at capacity and all connections
        are active.
        """
        # Try reuse an idle connection for this host
        for conn in self._connections.values():
            if conn.host == host and not conn.is_active:
                conn.is_active = True
                conn.last_used = time.time()
                return conn
        # Create new if room
        if len(self._connections) >= self.max_size:
            raise RuntimeError("Connection pool exhausted")
        now = time.time()
        conn = Connection(
            id=uuid.uuid4().hex[:12],
            host=host,
            created_at=now,
            last_used=now,
            is_active=True,
        )
        self._connections[conn.id] = conn
        return conn

    def release(self, conn: Connection) -> None:
        """Return *conn* to the pool (mark idle)."""
        if conn.id in self._connections:
            conn.is_active = False
            conn.last_used = time.time()

    def close(self, conn_id: str) -> bool:
        """Close and remove a connection by id. Returns ``True`` if found."""
        return self._connections.pop(conn_id, None) is not None

    def evict_idle(self) -> int:
        """Remove connections idle longer than ``max_idle_time``. Returns count."""
        now = time.time()
        to_remove = [
            cid
            for cid, c in self._connections.items()
            if not c.is_active and (now - c.last_used) > self.max_idle_time
        ]
        for cid in to_remove:
            del self._connections[cid]
        return len(to_remove)

    def stats(self) -> dict[str, int]:
        """Return pool statistics."""
        active = sum(1 for c in self._connections.values() if c.is_active)
        total = len(self._connections)
        return {"active": active, "idle": total - active, "total": total}
