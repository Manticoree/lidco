"""Tests for Q296 ComposeManager."""
import unittest

from lidco.containers.compose import ComposeManager


class TestComposeManager(unittest.TestCase):
    def setUp(self):
        self.mgr = ComposeManager()

    # -- add / remove / list -----------------------------------------------

    def test_add_service_basic(self):
        svc = self.mgr.add_service("web", "nginx:latest", ["8080:80"])
        self.assertEqual(svc.name, "web")
        self.assertEqual(svc.image, "nginx:latest")
        self.assertEqual(svc.ports, ["8080:80"])

    def test_add_service_with_all_options(self):
        svc = self.mgr.add_service(
            "api",
            "myapi:1.0",
            ["3000:3000"],
            environment={"NODE_ENV": "production"},
            depends_on=["db"],
            volumes=["./data:/data"],
            networks=["backend"],
            command="npm start",
        )
        self.assertEqual(svc.environment, {"NODE_ENV": "production"})
        self.assertEqual(svc.depends_on, ["db"])
        self.assertEqual(svc.volumes, ["./data:/data"])
        self.assertEqual(svc.networks, ["backend"])
        self.assertEqual(svc.command, "npm start")

    def test_remove_service_existing(self):
        self.mgr.add_service("web", "nginx:latest")
        self.assertTrue(self.mgr.remove_service("web"))

    def test_remove_service_missing(self):
        self.assertFalse(self.mgr.remove_service("nonexistent"))

    def test_list_services(self):
        self.mgr.add_service("web", "nginx:latest")
        self.mgr.add_service("db", "postgres:16")
        self.assertEqual(self.mgr.list_services(), ["db", "web"])

    def test_get_service(self):
        self.mgr.add_service("web", "nginx:latest")
        svc = self.mgr.get_service("web")
        self.assertIsNotNone(svc)
        self.assertEqual(svc.image, "nginx:latest")

    def test_get_service_missing(self):
        self.assertIsNone(self.mgr.get_service("nope"))

    def test_add_replaces_existing(self):
        self.mgr.add_service("web", "nginx:1.0")
        self.mgr.add_service("web", "nginx:2.0")
        self.assertEqual(self.mgr.get_service("web").image, "nginx:2.0")
        self.assertEqual(len(self.mgr.list_services()), 1)

    # -- generate ----------------------------------------------------------

    def test_generate_empty(self):
        result = self.mgr.generate()
        self.assertIn('version: "3.9"', result)

    def test_generate_with_service(self):
        self.mgr.add_service("web", "nginx:latest", ["80:80"])
        result = self.mgr.generate()
        self.assertIn("services:", result)
        self.assertIn("web:", result)
        self.assertIn("nginx:latest", result)
        self.assertIn('"80:80"', result)

    def test_generate_includes_networks(self):
        self.mgr.add_service("web", "nginx:latest", networks=["frontend"])
        result = self.mgr.generate()
        self.assertIn("networks:", result)
        self.assertIn("frontend:", result)

    # -- validate ----------------------------------------------------------

    def test_validate_empty_services(self):
        errors = self.mgr.validate()
        self.assertIn("No services defined", errors)

    def test_validate_missing_dependency(self):
        self.mgr.add_service("web", "nginx:latest", depends_on=["db"])
        errors = self.mgr.validate()
        self.assertTrue(any("unknown service" in e for e in errors))

    def test_validate_port_conflict(self):
        self.mgr.add_service("web1", "nginx:latest", ["8080:80"])
        self.mgr.add_service("web2", "nginx:latest", ["8080:81"])
        errors = self.mgr.validate()
        self.assertTrue(any("Port conflict" in e for e in errors))

    def test_validate_valid_config(self):
        self.mgr.add_service("db", "postgres:16", ["5432:5432"])
        self.mgr.add_service("web", "nginx:latest", ["80:80"], depends_on=["db"])
        errors = self.mgr.validate()
        self.assertEqual(errors, [])

    # -- dependencies ------------------------------------------------------

    def test_dependencies_direct(self):
        self.mgr.add_service("db", "postgres:16")
        self.mgr.add_service("web", "nginx:latest", depends_on=["db"])
        deps = self.mgr.dependencies("web")
        self.assertIn("db", deps)

    def test_dependencies_transitive(self):
        self.mgr.add_service("redis", "redis:7")
        self.mgr.add_service("db", "postgres:16", depends_on=["redis"])
        self.mgr.add_service("web", "nginx:latest", depends_on=["db"])
        deps = self.mgr.dependencies("web")
        self.assertIn("redis", deps)
        self.assertIn("db", deps)

    def test_dependencies_unknown_service_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.dependencies("nonexistent")

    def test_dependencies_no_deps(self):
        self.mgr.add_service("web", "nginx:latest")
        deps = self.mgr.dependencies("web")
        self.assertEqual(deps, [])

    # -- networks ----------------------------------------------------------

    def test_networks_empty(self):
        self.assertEqual(self.mgr.networks(), [])

    def test_networks_from_services(self):
        self.mgr.add_service("web", "nginx:latest", networks=["frontend"])
        self.assertIn("frontend", self.mgr.networks())

    def test_networks_explicit(self):
        self.mgr.add_network("backend", driver="overlay")
        self.assertIn("backend", self.mgr.networks())


if __name__ == "__main__":
    unittest.main()
