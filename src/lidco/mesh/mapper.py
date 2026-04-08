"""Service Mapper — discover services, call graph, dependency map, version matrix, health status."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence


class HealthStatus(Enum):
    """Health status of a service."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ServiceInfo:
    """Metadata for a single discovered service."""

    name: str
    version: str = "0.0.0"
    host: str = "localhost"
    port: int = 8080
    protocol: str = "http"
    health: HealthStatus = HealthStatus.UNKNOWN
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ServiceEdge:
    """Directed edge in the call graph (source -> target)."""

    source: str
    target: str
    protocol: str = "http"
    weight: float = 1.0


@dataclass(frozen=True)
class DependencyMap:
    """Full dependency map for the mesh."""

    services: tuple[ServiceInfo, ...]
    edges: tuple[ServiceEdge, ...]
    generated_at: float = 0.0


@dataclass(frozen=True)
class VersionEntry:
    """Version info for a service."""

    service: str
    version: str
    instances: int = 1


@dataclass(frozen=True)
class VersionMatrix:
    """Version matrix across all services."""

    entries: tuple[VersionEntry, ...]


class ServiceMapper:
    """Discover services, build call graph, dependency map, version matrix, health."""

    def __init__(self, services: Sequence[ServiceInfo] | None = None,
                 edges: Sequence[ServiceEdge] | None = None) -> None:
        self._services: dict[str, ServiceInfo] = {}
        self._edges: list[ServiceEdge] = []
        for svc in (services or []):
            self._services[svc.name] = svc
        self._edges.extend(edges or [])

    # -- mutators (return new mapper for immutability-friendly API) --

    def add_service(self, service: ServiceInfo) -> ServiceMapper:
        """Return a new mapper with the service added."""
        new_services = {**self._services, service.name: service}
        mapper = ServiceMapper()
        mapper._services = new_services
        mapper._edges = list(self._edges)
        return mapper

    def add_edge(self, edge: ServiceEdge) -> ServiceMapper:
        """Return a new mapper with the edge added."""
        mapper = ServiceMapper()
        mapper._services = dict(self._services)
        mapper._edges = list(self._edges) + [edge]
        return mapper

    def register_service(self, service: ServiceInfo) -> None:
        """Register a service in-place (convenience for builders)."""
        self._services[service.name] = service

    def register_edge(self, edge: ServiceEdge) -> None:
        """Register an edge in-place (convenience for builders)."""
        self._edges.append(edge)

    # -- queries --

    def discover(self) -> list[ServiceInfo]:
        """Return all discovered services."""
        return list(self._services.values())

    def get_service(self, name: str) -> Optional[ServiceInfo]:
        """Lookup service by name."""
        return self._services.get(name)

    def call_graph(self) -> list[ServiceEdge]:
        """Return the full call graph as a list of edges."""
        return list(self._edges)

    def dependencies_of(self, service_name: str) -> list[str]:
        """Return names of services that *service_name* depends on (outgoing edges)."""
        return [e.target for e in self._edges if e.source == service_name]

    def dependents_of(self, service_name: str) -> list[str]:
        """Return names of services that depend on *service_name* (incoming edges)."""
        return [e.source for e in self._edges if e.target == service_name]

    def dependency_map(self) -> DependencyMap:
        """Build the full dependency map."""
        return DependencyMap(
            services=tuple(self._services.values()),
            edges=tuple(self._edges),
            generated_at=time.time(),
        )

    def version_matrix(self) -> VersionMatrix:
        """Build a version matrix across all services."""
        entries = tuple(
            VersionEntry(service=s.name, version=s.version, instances=1)
            for s in self._services.values()
        )
        return VersionMatrix(entries=entries)

    def health_status(self) -> dict[str, HealthStatus]:
        """Return health status for each service."""
        return {name: svc.health for name, svc in self._services.items()}

    def unhealthy_services(self) -> list[ServiceInfo]:
        """Return services that are not healthy."""
        return [
            svc for svc in self._services.values()
            if svc.health in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)
        ]
