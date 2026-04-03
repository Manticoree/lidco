"""Tests for Q255 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q255_cmds as q255_mod


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.registry import CommandRegistry
        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q255_mod.register(reg)
        self._commands = reg._commands


class TestDepGraphCmd(_CmdTestBase):
    def test_add_node(self):
        handler = self._commands["dep-graph"].handler
        result = asyncio.run(handler("add requests 2.31.0"))
        self.assertIn("Added requests", result)
        self.assertIn("2.31.0", result)

    def test_add_transitive(self):
        handler = self._commands["dep-graph"].handler
        result = asyncio.run(handler("add urllib3 1.0 --transitive"))
        self.assertIn("transitive", result)

    def test_show(self):
        handler = self._commands["dep-graph"].handler
        result = asyncio.run(handler("show"))
        self.assertIn("node(s)", result)
        self.assertIn("edge(s)", result)

    def test_link(self):
        handler = self._commands["dep-graph"].handler
        result = asyncio.run(handler("link requests urllib3 >=1.0"))
        self.assertIn("Linked requests -> urllib3", result)
        self.assertIn(">=1.0", result)

    def test_link_missing_target(self):
        handler = self._commands["dep-graph"].handler
        result = asyncio.run(handler("link onlysource"))
        self.assertIn("Usage", result)

    def test_add_no_args(self):
        handler = self._commands["dep-graph"].handler
        result = asyncio.run(handler("add"))
        self.assertIn("Usage", result)

    def test_usage(self):
        handler = self._commands["dep-graph"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestResolveDepsCmd(_CmdTestBase):
    def test_conflicts(self):
        handler = self._commands["resolve-deps"].handler
        result = asyncio.run(handler("conflicts a:>=1.0 a:>=2.0"))
        self.assertIn("conflict", result.lower())

    def test_conflicts_no_args(self):
        handler = self._commands["resolve-deps"].handler
        result = asyncio.run(handler("conflicts"))
        self.assertIn("No edges", result)

    def test_resolve(self):
        handler = self._commands["resolve-deps"].handler
        result = asyncio.run(handler("resolve a:1.0 a:2.0"))
        self.assertIn("a = 2.0", result)

    def test_resolve_no_args(self):
        handler = self._commands["resolve-deps"].handler
        result = asyncio.run(handler("resolve"))
        self.assertIn("Usage", result)

    def test_upgrades(self):
        handler = self._commands["resolve-deps"].handler
        result = asyncio.run(handler("upgrades foo:1.2.3"))
        self.assertIn("suggestion", result.lower())
        self.assertIn("1.2.4", result)

    def test_upgrades_no_args(self):
        handler = self._commands["resolve-deps"].handler
        result = asyncio.run(handler("upgrades"))
        self.assertIn("No packages", result)

    def test_usage(self):
        handler = self._commands["resolve-deps"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestLicenseAuditCmd(_CmdTestBase):
    def test_add(self):
        handler = self._commands["license-audit"].handler
        result = asyncio.run(handler("add requests MIT permissive"))
        self.assertIn("Added requests", result)

    def test_check(self):
        handler = self._commands["license-audit"].handler
        result = asyncio.run(handler("check MIT"))
        self.assertIn("compatible", result.lower())

    def test_check_no_args(self):
        handler = self._commands["license-audit"].handler
        result = asyncio.run(handler("check"))
        self.assertIn("Usage", result)

    def test_sbom(self):
        handler = self._commands["license-audit"].handler
        result = asyncio.run(handler("sbom"))
        self.assertIn("SBOM", result)

    def test_summary(self):
        handler = self._commands["license-audit"].handler
        result = asyncio.run(handler("summary"))
        self.assertIn("No license data", result)

    def test_usage(self):
        handler = self._commands["license-audit"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestPlanUpdatesCmd(_CmdTestBase):
    def test_plan(self):
        handler = self._commands["plan-updates"].handler
        result = asyncio.run(handler("plan a:1.0:2.0"))
        self.assertIn("update", result.lower())
        self.assertIn("BREAKING", result)

    def test_plan_no_args(self):
        handler = self._commands["plan-updates"].handler
        result = asyncio.run(handler("plan"))
        self.assertIn("Usage", result)

    def test_risk(self):
        handler = self._commands["plan-updates"].handler
        result = asyncio.run(handler("risk pkg 1.0 1.1"))
        self.assertIn("low", result)

    def test_risk_no_args(self):
        handler = self._commands["plan-updates"].handler
        result = asyncio.run(handler("risk"))
        self.assertIn("Usage", result)

    def test_rollback(self):
        handler = self._commands["plan-updates"].handler
        result = asyncio.run(handler("rollback a:1.0:2.0"))
        self.assertIn("rollback", result.lower())
        self.assertIn("a", result)

    def test_rollback_no_args(self):
        handler = self._commands["plan-updates"].handler
        result = asyncio.run(handler("rollback"))
        self.assertIn("Usage", result)

    def test_usage(self):
        handler = self._commands["plan-updates"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
