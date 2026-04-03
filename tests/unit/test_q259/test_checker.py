"""Tests for PermissionChecker (Q259)."""
from __future__ import annotations

import unittest

from lidco.rbac.roles import RoleRegistry
from lidco.rbac.checker import CheckResult, PermissionChecker


class TestCheckResult(unittest.TestCase):
    def test_frozen(self):
        r = CheckResult(allowed=True, reason="ok", role="admin", permission="*")
        with self.assertRaises(AttributeError):
            r.allowed = False  # type: ignore[misc]


class TestPermissionChecker(unittest.TestCase):
    def setUp(self):
        self.registry = RoleRegistry()
        self.checker = PermissionChecker(self.registry)

    def test_default_role_is_viewer(self):
        self.assertEqual(self.checker.get_role("unknown_user"), "viewer")

    def test_assign_role(self):
        self.assertTrue(self.checker.assign_role("alice", "admin"))
        self.assertEqual(self.checker.get_role("alice"), "admin")

    def test_assign_invalid_role(self):
        self.assertFalse(self.checker.assign_role("bob", "nonexistent"))

    def test_check_admin_allowed(self):
        self.checker.assign_role("alice", "admin")
        result = self.checker.check("alice", "tool.use")
        self.assertTrue(result.allowed)
        self.assertEqual(result.role, "admin")

    def test_check_viewer_denied(self):
        result = self.checker.check("guest", "tool.use")
        self.assertFalse(result.allowed)
        self.assertIn("denied", result.reason)

    def test_check_viewer_read_allowed(self):
        result = self.checker.check("guest", "read")
        self.assertTrue(result.allowed)

    def test_check_tool(self):
        self.checker.assign_role("dev", "developer")
        result = self.checker.check_tool("dev", "some_tool")
        self.assertTrue(result.allowed)

    def test_check_file(self):
        result = self.checker.check_file("guest", "/etc/passwd")
        # viewer has "read" but check_file checks "file.read"
        self.assertFalse(result.allowed)

    def test_check_command(self):
        self.checker.assign_role("dev", "developer")
        result = self.checker.check_command("dev", "/deploy")
        self.assertTrue(result.allowed)

    def test_history_recorded(self):
        self.checker.check("a", "read")
        self.checker.check("b", "write")
        h = self.checker.history()
        self.assertEqual(len(h), 2)

    def test_history_limit(self):
        for i in range(20):
            self.checker.check(f"u{i}", "read")
        h = self.checker.history(limit=5)
        self.assertEqual(len(h), 5)

    def test_summary(self):
        self.checker.assign_role("x", "admin")
        self.checker.check("x", "tool.use")
        s = self.checker.summary()
        self.assertEqual(s["total_checks"], 1)
        self.assertEqual(s["allowed"], 1)
        self.assertEqual(s["users"], 1)


if __name__ == "__main__":
    unittest.main()
