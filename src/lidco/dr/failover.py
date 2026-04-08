"""
Failover Orchestrator -- automated failover with health detection,
DNS switching, data sync verification, and notification.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class NodeStatus(Enum):
    """Health status of a node."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class FailoverStatus(Enum):
    """Status of a failover operation."""

    IDLE = "idle"
    DETECTING = "detecting"
    SWITCHING = "switching"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Node:
    """A node that can be primary or secondary."""

    node_id: str
    name: str
    endpoint: str
    is_primary: bool = False
    status: NodeStatus = NodeStatus.UNKNOWN
    last_check: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("node_id must not be empty")
        if not self.endpoint:
            raise ValueError("endpoint must not be empty")


@dataclass
class HealthCheck:
    """Result of a health check."""

    node_id: str
    status: NodeStatus
    checked_at: float
    latency_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailoverEvent:
    """Record of a failover event."""

    event_id: str
    status: FailoverStatus
    from_node: str
    to_node: str
    started_at: float
    completed_at: float = 0.0
    reason: str = ""
    data_sync_verified: bool = False
    dns_switched: bool = False
    notifications_sent: int = 0
    error: str = ""


class FailoverOrchestrator:
    """Orchestrates automated failover with health detection,
    DNS switching, data sync verification, and notifications."""

    def __init__(
        self,
        check_interval: float = 10.0,
        failure_threshold: int = 3,
    ) -> None:
        self._check_interval = check_interval
        self._failure_threshold = failure_threshold
        self._nodes: dict[str, Node] = {}
        self._events: list[FailoverEvent] = []
        self._failure_counts: dict[str, int] = {}
        self._health_checker: Callable[[Node], HealthCheck] | None = None
        self._dns_switcher: Callable[[str, str], bool] | None = None
        self._data_verifier: Callable[[str, str], bool] | None = None
        self._notifier: Callable[[FailoverEvent], None] | None = None

    def register_node(self, node: Node) -> None:
        """Register a node for failover management."""
        self._nodes[node.node_id] = node
        self._failure_counts[node.node_id] = 0

    def remove_node(self, node_id: str) -> bool:
        """Remove a node from management."""
        if node_id in self._nodes:
            del self._nodes[node_id]
            self._failure_counts.pop(node_id, None)
            return True
        return False

    @property
    def nodes(self) -> dict[str, Node]:
        return dict(self._nodes)

    @property
    def events(self) -> list[FailoverEvent]:
        return list(self._events)

    def set_health_checker(self, checker: Callable[[Node], HealthCheck]) -> None:
        self._health_checker = checker

    def set_dns_switcher(self, switcher: Callable[[str, str], bool]) -> None:
        self._dns_switcher = switcher

    def set_data_verifier(self, verifier: Callable[[str, str], bool]) -> None:
        self._data_verifier = verifier

    def set_notifier(self, notifier: Callable[[FailoverEvent], None]) -> None:
        self._notifier = notifier

    def get_primary(self) -> Node | None:
        """Return the current primary node."""
        for node in self._nodes.values():
            if node.is_primary:
                return node
        return None

    def get_secondaries(self) -> list[Node]:
        """Return all secondary (non-primary) nodes."""
        return [n for n in self._nodes.values() if not n.is_primary]

    def check_health(self, node_id: str) -> HealthCheck:
        """Check health of a specific node."""
        node = self._nodes.get(node_id)
        if node is None:
            return HealthCheck(
                node_id=node_id,
                status=NodeStatus.UNKNOWN,
                checked_at=time.time(),
                details={"error": "Node not found"},
            )

        if self._health_checker:
            result = self._health_checker(node)
        else:
            result = HealthCheck(
                node_id=node_id,
                status=NodeStatus.HEALTHY,
                checked_at=time.time(),
            )

        node.status = result.status
        node.last_check = result.checked_at

        if result.status == NodeStatus.UNHEALTHY:
            self._failure_counts[node_id] = self._failure_counts.get(node_id, 0) + 1
        else:
            self._failure_counts[node_id] = 0

        return result

    def check_all_health(self) -> list[HealthCheck]:
        """Check health of all registered nodes."""
        return [self.check_health(nid) for nid in self._nodes]

    def needs_failover(self) -> bool:
        """Check if failover is needed based on primary health."""
        primary = self.get_primary()
        if primary is None:
            return False
        count = self._failure_counts.get(primary.node_id, 0)
        return count >= self._failure_threshold

    def execute_failover(self, target_id: str | None = None) -> FailoverEvent:
        """Execute a failover from the current primary to a target secondary."""
        event_id = uuid.uuid4().hex[:12]
        start = time.time()

        primary = self.get_primary()
        if primary is None:
            evt = FailoverEvent(
                event_id=event_id,
                status=FailoverStatus.FAILED,
                from_node="",
                to_node=target_id or "",
                started_at=start,
                completed_at=time.time(),
                error="No primary node configured",
            )
            self._events.append(evt)
            return evt

        if target_id:
            target = self._nodes.get(target_id)
        else:
            secondaries = self.get_secondaries()
            healthy = [s for s in secondaries if s.status == NodeStatus.HEALTHY]
            target = healthy[0] if healthy else (secondaries[0] if secondaries else None)

        if target is None:
            evt = FailoverEvent(
                event_id=event_id,
                status=FailoverStatus.FAILED,
                from_node=primary.node_id,
                to_node="",
                started_at=start,
                completed_at=time.time(),
                error="No suitable target node available",
            )
            self._events.append(evt)
            return evt

        data_ok = True
        if self._data_verifier:
            data_ok = self._data_verifier(primary.node_id, target.node_id)

        dns_ok = True
        if self._dns_switcher:
            dns_ok = self._dns_switcher(primary.endpoint, target.endpoint)

        if not data_ok:
            evt = FailoverEvent(
                event_id=event_id,
                status=FailoverStatus.FAILED,
                from_node=primary.node_id,
                to_node=target.node_id,
                started_at=start,
                completed_at=time.time(),
                error="Data sync verification failed",
                data_sync_verified=False,
            )
            self._events.append(evt)
            return evt

        primary.is_primary = False
        target.is_primary = True

        evt = FailoverEvent(
            event_id=event_id,
            status=FailoverStatus.COMPLETED,
            from_node=primary.node_id,
            to_node=target.node_id,
            started_at=start,
            completed_at=time.time(),
            data_sync_verified=data_ok,
            dns_switched=dns_ok,
        )

        if self._notifier:
            try:
                self._notifier(evt)
                evt.notifications_sent = 1
            except Exception:
                pass

        self._events.append(evt)
        return evt

    def rollback(self, event_id: str) -> FailoverEvent | None:
        """Rollback a completed failover."""
        original = None
        for e in self._events:
            if e.event_id == event_id:
                original = e
                break

        if original is None or original.status != FailoverStatus.COMPLETED:
            return None

        reverse = self.execute_failover(target_id=original.from_node)
        if reverse.status == FailoverStatus.COMPLETED:
            original.status = FailoverStatus.ROLLED_BACK
        return reverse
