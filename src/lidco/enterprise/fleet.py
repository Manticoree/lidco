"""Fleet management for multiple LIDCO instances."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Instance:
    """A managed LIDCO instance."""

    id: str
    name: str
    version: str
    status: str = "healthy"
    last_heartbeat: float = 0.0
    metadata: dict = field(default_factory=dict)


class FleetManager:
    """Manage multiple LIDCO instances with health monitoring."""

    def __init__(self, heartbeat_timeout: float = 300.0) -> None:
        self._instances: dict[str, Instance] = {}
        self._heartbeat_timeout = heartbeat_timeout

    def register(
        self,
        name: str,
        version: str,
        metadata: dict | None = None,
    ) -> Instance:
        """Register a new instance."""
        instance = Instance(
            id=uuid.uuid4().hex[:12],
            name=name,
            version=version,
            status="healthy",
            last_heartbeat=time.time(),
            metadata=metadata or {},
        )
        self._instances[instance.id] = instance
        return instance

    def deregister(self, instance_id: str) -> bool:
        """Remove an instance. Returns True if it existed."""
        if instance_id in self._instances:
            del self._instances[instance_id]
            return True
        return False

    def heartbeat(self, instance_id: str) -> Instance | None:
        """Update heartbeat timestamp. Returns instance or None."""
        inst = self._instances.get(instance_id)
        if inst is None:
            return None
        inst.last_heartbeat = time.time()
        if inst.status == "offline":
            inst.status = "healthy"
        return inst

    def get(self, instance_id: str) -> Instance | None:
        """Get an instance by ID."""
        return self._instances.get(instance_id)

    def check_health(self) -> dict:
        """Scan instances and mark timed-out ones as offline."""
        now = time.time()
        healthy = 0
        degraded = 0
        offline = 0
        for inst in self._instances.values():
            if now - inst.last_heartbeat > self._heartbeat_timeout:
                inst.status = "offline"
            if inst.status == "healthy":
                healthy += 1
            elif inst.status == "degraded":
                degraded += 1
            else:
                offline += 1
        return {"healthy": healthy, "degraded": degraded, "offline": offline}

    def by_status(self, status: str) -> list[Instance]:
        """Filter instances by status."""
        return [i for i in self._instances.values() if i.status == status]

    def by_version(self, version: str) -> list[Instance]:
        """Filter instances by version."""
        return [i for i in self._instances.values() if i.version == version]

    def all_instances(self) -> list[Instance]:
        """Return all instances."""
        return list(self._instances.values())

    def summary(self) -> dict:
        """Return fleet summary with counts."""
        by_status: dict[str, int] = {}
        by_version: dict[str, int] = {}
        for inst in self._instances.values():
            by_status[inst.status] = by_status.get(inst.status, 0) + 1
            by_version[inst.version] = by_version.get(inst.version, 0) + 1
        return {
            "total": len(self._instances),
            "by_status": by_status,
            "by_version": by_version,
        }
