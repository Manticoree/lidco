"""Tests for Q296 CLI commands."""
import asyncio
import unittest
from unittest.mock import MagicMock


class _FakeRegistry:
    """Minimal registry mock for testing command registration."""

    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler) -> None:
        self.commands[name] = (desc, handler)


class TestQ296Commands(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q296_cmds import register_q296_commands

        self.registry = _FakeRegistry()
        register_q296_commands(self.registry)

    # -- registration ------------------------------------------------------

    def test_all_commands_registered(self):
        expected = {"dockerfile", "compose", "k8s", "container-debug"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    # -- /dockerfile -------------------------------------------------------

    def test_dockerfile_no_args(self):
        _, handler = self.registry.commands["dockerfile"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_dockerfile_generate_python(self):
        _, handler = self.registry.commands["dockerfile"]
        result = asyncio.run(handler("generate python"))
        self.assertIn("FROM python", result)

    def test_dockerfile_generate_with_framework(self):
        _, handler = self.registry.commands["dockerfile"]
        result = asyncio.run(handler("generate python flask"))
        self.assertIn("flask", result.lower())

    def test_dockerfile_generate_unsupported(self):
        _, handler = self.registry.commands["dockerfile"]
        result = asyncio.run(handler("generate cobol"))
        self.assertIn("Error", result)

    def test_dockerfile_unknown_subcmd(self):
        _, handler = self.registry.commands["dockerfile"]
        result = asyncio.run(handler("foobar"))
        self.assertIn("Unknown", result)

    # -- /compose ----------------------------------------------------------

    def test_compose_no_args(self):
        _, handler = self.registry.commands["compose"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_compose_add_and_list(self):
        _, handler = self.registry.commands["compose"]
        asyncio.run(handler("add web nginx:latest --port 80:80"))
        result = asyncio.run(handler("list"))
        self.assertIn("web", result)

    def test_compose_generate(self):
        _, handler = self.registry.commands["compose"]
        asyncio.run(handler("add db postgres:16"))
        result = asyncio.run(handler("generate"))
        self.assertIn("postgres", result)

    def test_compose_validate_empty(self):
        # Need fresh state — create new registry
        from lidco.cli.commands.q296_cmds import register_q296_commands
        reg2 = _FakeRegistry()
        register_q296_commands(reg2)
        _, handler = reg2.commands["compose"]
        result = asyncio.run(handler("validate"))
        self.assertIn("No services", result)

    # -- /k8s --------------------------------------------------------------

    def test_k8s_no_args(self):
        _, handler = self.registry.commands["k8s"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_k8s_deployment(self):
        _, handler = self.registry.commands["k8s"]
        result = asyncio.run(handler("deployment myapp myapp:1.0 --replicas 3"))
        self.assertIn("Deployment", result)
        self.assertIn("myapp", result)

    def test_k8s_service(self):
        _, handler = self.registry.commands["k8s"]
        result = asyncio.run(handler("service myapp 80"))
        self.assertIn("Service", result)

    def test_k8s_ingress(self):
        _, handler = self.registry.commands["k8s"]
        result = asyncio.run(handler("ingress myapp example.com --path /api"))
        self.assertIn("Ingress", result)

    def test_k8s_helm(self):
        _, handler = self.registry.commands["k8s"]
        result = asyncio.run(handler("helm myapp"))
        self.assertIn("Helm chart", result)

    # -- /container-debug --------------------------------------------------

    def test_container_debug_no_args(self):
        _, handler = self.registry.commands["container-debug"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_container_debug_port_forward(self):
        _, handler = self.registry.commands["container-debug"]
        result = asyncio.run(handler("port-forward abc 3000 8080"))
        self.assertIn("configured", result)

    def test_container_debug_unknown_subcmd(self):
        _, handler = self.registry.commands["container-debug"]
        result = asyncio.run(handler("foobar"))
        self.assertIn("Unknown", result)


if __name__ == "__main__":
    unittest.main()
