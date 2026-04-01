"""Cloud provider resource listing and management."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CloudProvider(str, Enum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


@dataclass(frozen=True)
class CloudResource:
    id: str
    name: str
    provider: CloudProvider
    resource_type: str
    region: str = ""
    status: str = "active"
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class LogEntry:
    timestamp: float
    message: str
    level: str = "INFO"
    source: str = ""


_counter: int = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"res_{_counter}"


class CloudConnector:
    """Cloud provider resource listing and management."""

    def __init__(self) -> None:
        self._resources: dict[str, CloudResource] = {}
        self._logs: list[LogEntry] = []
        self._credentials: dict[str, dict[str, str]] = {}

    def add_credential(self, provider: CloudProvider, key: str, value: str) -> None:
        """Store a credential for a cloud provider."""
        existing = self._credentials.get(provider.value, {})
        self._credentials = {
            **self._credentials,
            provider.value: {**existing, key: value},
        }

    def has_credential(self, provider: CloudProvider) -> bool:
        """Check if credentials exist for a provider."""
        return provider.value in self._credentials

    def register_resource(
        self,
        name: str,
        provider: CloudProvider,
        resource_type: str,
        region: str = "",
        status: str = "active",
    ) -> CloudResource:
        """Register a cloud resource."""
        resource = CloudResource(
            id=_next_id(),
            name=name,
            provider=provider,
            resource_type=resource_type,
            region=region,
            status=status,
        )
        self._resources = {**self._resources, resource.id: resource}
        return resource

    def list_resources(
        self,
        provider: CloudProvider | None = None,
        resource_type: str | None = None,
    ) -> list[CloudResource]:
        """List resources, optionally filtered."""
        resources = list(self._resources.values())
        if provider is not None:
            resources = [r for r in resources if r.provider == provider]
        if resource_type is not None:
            resources = [r for r in resources if r.resource_type == resource_type]
        return resources

    def get_resource(self, resource_id: str) -> CloudResource | None:
        """Get a resource by ID."""
        return self._resources.get(resource_id)

    def add_log(
        self, message: str, level: str = "INFO", source: str = ""
    ) -> LogEntry:
        """Add a log entry."""
        entry = LogEntry(
            timestamp=time.time(), message=message, level=level, source=source
        )
        self._logs = [*self._logs, entry]
        return entry

    def tail_logs(
        self, source: str | None = None, limit: int = 50
    ) -> list[LogEntry]:
        """Tail recent logs, optionally filtered by source."""
        logs = self._logs
        if source is not None:
            logs = [lg for lg in logs if lg.source == source]
        return logs[-limit:]

    def invoke_function(
        self, resource_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Invoke a cloud function resource."""
        return {"resource": resource_id, "status": "invoked", "payload": payload}

    def summary(self) -> str:
        """Return human-readable summary."""
        if not self._resources:
            return "No cloud resources."
        parts = [f"Cloud resources: {len(self._resources)}"]
        for res in list(self._resources.values())[-10:]:
            parts.append(
                f"  - {res.id}: {res.name} [{res.provider.value}] {res.resource_type} ({res.status})"
            )
        return "\n".join(parts)
