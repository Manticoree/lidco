"""Tests for lidco.cli.commands.q317_cmds — /e2e-plan, /e2e-gen, /e2e-failure, /e2e-optimize."""

from __future__ import annotations

import asyncio
import unittest


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, object] = {}

    def register_async(self, name: str, desc: str, handler: object) -> None:
        self.commands[name] = handler


class TestQ317CommandRegistration(unittest.TestCase):
    def test_all_commands_registered(self) -> None:
        from lidco.cli.commands.q317_cmds import register_q317_commands

        reg = _FakeRegistry()
        register_q317_commands(reg)
        expected = {"e2e-plan", "e2e-gen", "e2e-failure", "e2e-optimize"}
        self.assertEqual(set(reg.commands.keys()), expected)


class TestE2EPlanHandler(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q317_cmds import register_q317_commands

        reg = _FakeRegistry()
        register_q317_commands(reg)
        return reg.commands["e2e-plan"]

    def test_default_args(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("E2E Test Plan", result)
        self.assertIn("login", result)

    def test_custom_journeys(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("signup profile"))
        self.assertIn("signup", result)
        self.assertIn("profile", result)

    def test_step_duration_flag(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--step-duration 10 mytest"))
        self.assertIn("mytest", result)
        self.assertIn("20.0s", result)  # 2 steps * 10s


class TestE2EGenHandler(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q317_cmds import register_q317_commands

        reg = _FakeRegistry()
        register_q317_commands(reg)
        return reg.commands["e2e-gen"]

    def test_default_playwright(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("playwright", result)
        self.assertIn("page.goto", result)

    def test_cypress_framework(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--framework cypress my_test"))
        self.assertIn("cypress", result)
        self.assertIn("cy.visit", result)

    def test_custom_name(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("login_flow"))
        self.assertIn("login_flow", result)


class TestE2EFailureHandler(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q317_cmds import register_q317_commands

        reg = _FakeRegistry()
        register_q317_commands(reg)
        return reg.commands["e2e-failure"]

    def test_default(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("Failure Analysis", result)

    def test_with_error(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("my_test Element not found"))
        self.assertIn("my_test", result)
        self.assertIn("element_not_found", result)

    def test_timeout_error(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("t Timed out"))
        self.assertIn("timeout", result)


class TestE2EOptimizeHandler(unittest.TestCase):
    def _get_handler(self):
        from lidco.cli.commands.q317_cmds import register_q317_commands

        reg = _FakeRegistry()
        register_q317_commands(reg)
        return reg.commands["e2e-optimize"]

    def test_default(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("Optimization Report", result)
        self.assertIn("Speedup", result)

    def test_parallel_flag(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--parallel 2"))
        self.assertIn("Optimization Report", result)

    def test_changed_files_flag(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("--changed search.py"))
        self.assertIn("Selected", result)


if __name__ == "__main__":
    unittest.main()
