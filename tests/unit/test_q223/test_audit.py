"""Tests for lidco.permissions.audit."""
from __future__ import annotations

import json
import time
import unittest

from lidco.permissions.audit import AuditEntry, PermissionAudit


class TestAuditEntry(unittest.TestCase):
    def test_frozen(self) -> None:
        e = AuditEntry(
            id="a", timestamp=1.0, actor="user",
            action="read", scope="file", resource="/a.py",
            reason="testing", result="allowed",
        )
        with self.assertRaises(AttributeError):
            e.result = "denied"  # type: ignore[misc]


class TestPermissionAudit(unittest.TestCase):
    def setUp(self) -> None:
        self.audit = PermissionAudit()

    def test_log(self) -> None:
        entry = self.audit.log("user", "read", "file", "/a.py", "testing", "allowed")
        self.assertIsInstance(entry, AuditEntry)
        self.assertEqual(entry.actor, "user")
        self.assertEqual(entry.result, "allowed")

    def test_count(self) -> None:
        self.assertEqual(self.audit.count(), 0)
        self.audit.log("u", "a", "s", "r", "reason", "allowed")
        self.assertEqual(self.audit.count(), 1)

    def test_query_all(self) -> None:
        self.audit.log("user", "read", "file", "/a.py", "r", "allowed")
        self.audit.log("admin", "write", "dir", "/src", "r", "denied")
        self.assertEqual(len(self.audit.query()), 2)

    def test_query_by_actor(self) -> None:
        self.audit.log("user", "read", "file", "/a.py", "r", "allowed")
        self.audit.log("admin", "write", "dir", "/src", "r", "denied")
        results = self.audit.query(actor="admin")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].actor, "admin")

    def test_query_by_result(self) -> None:
        self.audit.log("u", "a", "s", "r", "reason", "allowed")
        self.audit.log("u", "a", "s", "r", "reason", "denied")
        self.assertEqual(len(self.audit.query(result="denied")), 1)

    def test_query_by_scope(self) -> None:
        self.audit.log("u", "a", "file", "r", "reason", "allowed")
        self.audit.log("u", "a", "tool", "r", "reason", "denied")
        self.assertEqual(len(self.audit.query(scope="tool")), 1)

    def test_query_since(self) -> None:
        self.audit.log("u", "a", "s", "r", "reason", "allowed")
        cutoff = time.time()
        self.audit.log("u", "a", "s", "r", "reason", "denied")
        results = self.audit.query(since=cutoff)
        self.assertEqual(len(results), 1)

    def test_query_limit(self) -> None:
        for i in range(10):
            self.audit.log("u", "a", "s", "r", "reason", "allowed")
        self.assertEqual(len(self.audit.query(limit=3)), 3)

    def test_export_json(self) -> None:
        self.audit.log("u", "a", "s", "r", "reason", "allowed")
        data = json.loads(self.audit.export_json())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["actor"], "u")

    def test_clear(self) -> None:
        self.audit.log("u", "a", "s", "r", "reason", "allowed")
        self.assertEqual(self.audit.clear(), 1)
        self.assertEqual(self.audit.count(), 0)

    def test_summary(self) -> None:
        self.audit.log("user", "a", "s", "r", "reason", "allowed")
        self.audit.log("admin", "a", "s", "r", "reason", "denied")
        s = self.audit.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["by_result"]["allowed"], 1)
        self.assertEqual(s["by_actor"]["admin"], 1)

    def test_max_entries_trim(self) -> None:
        audit = PermissionAudit(max_entries=5)
        for i in range(10):
            audit.log("u", "a", "s", "r", "reason", "allowed")
        self.assertEqual(audit.count(), 5)
