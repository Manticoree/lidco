"""Tests for Q261 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q261_cmds as q261_mod


def _run(coro):
    return asyncio.run(coro)


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        q261_mod._state.clear()
        from lidco.cli.commands.registry import CommandRegistry
        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q261_mod.register(reg)
        self.audit_events = reg._commands["audit-events"].handler
        self.audit_query = reg._commands["audit-query"].handler
        self.audit_anomaly = reg._commands["audit-anomaly"].handler
        self.audit_dashboard = reg._commands["audit-dashboard"].handler


class TestAuditEventsCmd(_CmdTestBase):
    def test_list_empty(self):
        result = _run(self.audit_events("list"))
        self.assertIn("No audit events", result)

    def test_list_with_events(self):
        # Seed via the store
        store = q261_mod._get_store()
        store.append("auth", "alice", "login", "/session")
        result = _run(self.audit_events("list"))
        self.assertIn("alice", result)

    def test_get_missing(self):
        result = _run(self.audit_events("get nonexistent"))
        self.assertIn("not found", result)

    def test_verify(self):
        store = q261_mod._get_store()
        store.append("auth", "alice", "login", "/session")
        result = _run(self.audit_events("verify"))
        self.assertIn("1 valid", result)

    def test_export_json(self):
        store = q261_mod._get_store()
        store.append("auth", "alice", "login", "/session")
        result = _run(self.audit_events("export json"))
        self.assertIn("alice", result)

    def test_usage(self):
        result = _run(self.audit_events("badcmd"))
        self.assertIn("Usage", result)


class TestAuditQueryCmd(_CmdTestBase):
    def test_empty_args(self):
        result = _run(self.audit_query(""))
        self.assertIn("Usage", result)

    def test_query_by_actor(self):
        store = q261_mod._get_store()
        store.append("auth", "alice", "login", "/session")
        store.append("auth", "bob", "login", "/session")
        result = _run(self.audit_query("actor=alice"))
        self.assertIn("alice", result)


class TestAuditAnomalyCmd(_CmdTestBase):
    def test_detect_empty(self):
        result = _run(self.audit_anomaly("detect"))
        self.assertIn("No anomalies", result)

    def test_privilege(self):
        result = _run(self.audit_anomaly("privilege"))
        self.assertIn("No privilege", result)

    def test_usage(self):
        result = _run(self.audit_anomaly("badcmd"))
        self.assertIn("Usage", result)


class TestAuditDashboardCmd(_CmdTestBase):
    def test_view(self):
        result = _run(self.audit_dashboard(""))
        self.assertIn("Audit Dashboard", result)

    def test_risk(self):
        result = _run(self.audit_dashboard("risk"))
        self.assertIn("Risk score", result)

    def test_summary(self):
        result = _run(self.audit_dashboard("summary"))
        self.assertIn("Events", result)
