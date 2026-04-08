"""Tests for lidco.mesh.mapper — ServiceMapper."""

from __future__ import annotations

import unittest

from lidco.mesh.mapper import (
    DependencyMap,
    HealthStatus,
    ServiceEdge,
    ServiceInfo,
    ServiceMapper,
    VersionEntry,
    VersionMatrix,
)


class TestServiceInfo(unittest.TestCase):
    def test_defaults(self) -> None:
        svc = ServiceInfo(name="api")
        self.assertEqual(svc.name, "api")
        self.assertEqual(svc.version, "0.0.0")
        self.assertEqual(svc.health, HealthStatus.UNKNOWN)

    def test_custom_fields(self) -> None:
        svc = ServiceInfo(name="web", version="1.2.3", port=3000, health=HealthStatus.HEALTHY)
        self.assertEqual(svc.version, "1.2.3")
        self.assertEqual(svc.port, 3000)
        self.assertEqual(svc.health, HealthStatus.HEALTHY)

    def test_frozen(self) -> None:
        svc = ServiceInfo(name="db")
        with self.assertRaises(AttributeError):
            svc.name = "other"  # type: ignore[misc]


class TestServiceEdge(unittest.TestCase):
    def test_creation(self) -> None:
        edge = ServiceEdge(source="a", target="b", weight=2.0)
        self.assertEqual(edge.source, "a")
        self.assertEqual(edge.target, "b")
        self.assertEqual(edge.weight, 2.0)


class TestServiceMapper(unittest.TestCase):
    def _make_mapper(self) -> ServiceMapper:
        services = [
            ServiceInfo(name="api", version="1.0.0", health=HealthStatus.HEALTHY),
            ServiceInfo(name="db", version="2.0.0", health=HealthStatus.HEALTHY),
            ServiceInfo(name="cache", version="3.0.0", health=HealthStatus.DEGRADED),
        ]
        edges = [
            ServiceEdge(source="api", target="db"),
            ServiceEdge(source="api", target="cache"),
        ]
        return ServiceMapper(services=services, edges=edges)

    def test_discover(self) -> None:
        mapper = self._make_mapper()
        services = mapper.discover()
        names = {s.name for s in services}
        self.assertEqual(names, {"api", "db", "cache"})

    def test_get_service(self) -> None:
        mapper = self._make_mapper()
        svc = mapper.get_service("api")
        self.assertIsNotNone(svc)
        self.assertEqual(svc.name, "api")
        self.assertIsNone(mapper.get_service("nonexistent"))

    def test_call_graph(self) -> None:
        mapper = self._make_mapper()
        edges = mapper.call_graph()
        self.assertEqual(len(edges), 2)

    def test_dependencies_of(self) -> None:
        mapper = self._make_mapper()
        deps = mapper.dependencies_of("api")
        self.assertEqual(set(deps), {"db", "cache"})
        self.assertEqual(mapper.dependencies_of("db"), [])

    def test_dependents_of(self) -> None:
        mapper = self._make_mapper()
        dependents = mapper.dependents_of("db")
        self.assertEqual(dependents, ["api"])

    def test_dependency_map(self) -> None:
        mapper = self._make_mapper()
        dep_map = mapper.dependency_map()
        self.assertIsInstance(dep_map, DependencyMap)
        self.assertEqual(len(dep_map.services), 3)
        self.assertEqual(len(dep_map.edges), 2)
        self.assertGreater(dep_map.generated_at, 0)

    def test_version_matrix(self) -> None:
        mapper = self._make_mapper()
        matrix = mapper.version_matrix()
        self.assertIsInstance(matrix, VersionMatrix)
        self.assertEqual(len(matrix.entries), 3)
        names = {e.service for e in matrix.entries}
        self.assertEqual(names, {"api", "db", "cache"})

    def test_health_status(self) -> None:
        mapper = self._make_mapper()
        health = mapper.health_status()
        self.assertEqual(health["api"], HealthStatus.HEALTHY)
        self.assertEqual(health["cache"], HealthStatus.DEGRADED)

    def test_unhealthy_services(self) -> None:
        mapper = self._make_mapper()
        unhealthy = mapper.unhealthy_services()
        self.assertEqual(len(unhealthy), 1)
        self.assertEqual(unhealthy[0].name, "cache")

    def test_add_service_immutable(self) -> None:
        mapper = ServiceMapper()
        new_svc = ServiceInfo(name="new", version="1.0.0")
        mapper2 = mapper.add_service(new_svc)
        self.assertEqual(len(mapper.discover()), 0)
        self.assertEqual(len(mapper2.discover()), 1)

    def test_add_edge_immutable(self) -> None:
        mapper = ServiceMapper()
        edge = ServiceEdge(source="a", target="b")
        mapper2 = mapper.add_edge(edge)
        self.assertEqual(len(mapper.call_graph()), 0)
        self.assertEqual(len(mapper2.call_graph()), 1)

    def test_register_service_in_place(self) -> None:
        mapper = ServiceMapper()
        mapper.register_service(ServiceInfo(name="svc1"))
        self.assertEqual(len(mapper.discover()), 1)

    def test_register_edge_in_place(self) -> None:
        mapper = ServiceMapper()
        mapper.register_edge(ServiceEdge(source="a", target="b"))
        self.assertEqual(len(mapper.call_graph()), 1)

    def test_empty_mapper(self) -> None:
        mapper = ServiceMapper()
        self.assertEqual(mapper.discover(), [])
        self.assertEqual(mapper.call_graph(), [])
        self.assertEqual(mapper.unhealthy_services(), [])
        dep_map = mapper.dependency_map()
        self.assertEqual(len(dep_map.services), 0)


class TestHealthStatus(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(HealthStatus.HEALTHY.value, "healthy")
        self.assertEqual(HealthStatus.UNHEALTHY.value, "unhealthy")
        self.assertEqual(HealthStatus.DEGRADED.value, "degraded")
        self.assertEqual(HealthStatus.UNKNOWN.value, "unknown")


if __name__ == "__main__":
    unittest.main()
