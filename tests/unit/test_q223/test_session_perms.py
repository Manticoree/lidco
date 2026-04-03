"""Tests for lidco.permissions.session_perms."""
from __future__ import annotations

import unittest

from lidco.permissions.session_perms import PermissionDecision, SessionPermissions


class TestPermissionDecision(unittest.TestCase):
    def test_frozen(self) -> None:
        d = PermissionDecision(scope="file", resource="/a.py", action="allow")
        with self.assertRaises(AttributeError):
            d.action = "deny"  # type: ignore[misc]

    def test_defaults(self) -> None:
        d = PermissionDecision(scope="s", resource="r", action="allow")
        self.assertFalse(d.sticky)
        self.assertEqual(d.decided_at, 0.0)


class TestSessionPermissions(unittest.TestCase):
    def setUp(self) -> None:
        self.sp = SessionPermissions()

    def test_set_and_get(self) -> None:
        self.sp.set("file", "/a.py", "allow")
        d = self.sp.get("file", "/a.py")
        self.assertIsNotNone(d)
        self.assertEqual(d.action, "allow")

    def test_get_missing(self) -> None:
        self.assertIsNone(self.sp.get("file", "/none.py"))

    def test_check(self) -> None:
        self.sp.set("tool", "exec", "deny")
        self.assertEqual(self.sp.check("tool", "exec"), "deny")

    def test_check_missing(self) -> None:
        self.assertIsNone(self.sp.check("tool", "exec"))

    def test_reset_clears_non_sticky(self) -> None:
        self.sp.set("file", "/a.py", "allow")
        self.sp.set("file", "/b.py", "deny", sticky=True)
        removed = self.sp.reset()
        self.assertEqual(removed, 1)
        self.assertIsNone(self.sp.get("file", "/a.py"))
        self.assertIsNotNone(self.sp.get("file", "/b.py"))

    def test_reset_all(self) -> None:
        self.sp.set("file", "/a.py", "allow", sticky=True)
        self.sp.set("file", "/b.py", "deny")
        removed = self.sp.reset_all()
        self.assertEqual(removed, 2)
        self.assertEqual(len(self.sp.decisions()), 0)

    def test_export(self) -> None:
        self.sp.set("file", "/a.py", "allow")
        exported = self.sp.export()
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["scope"], "file")
        self.assertEqual(exported[0]["action"], "allow")
        self.assertIn("decided_at", exported[0])

    def test_decisions(self) -> None:
        self.sp.set("file", "/a.py", "allow")
        self.sp.set("tool", "exec", "deny")
        self.assertEqual(len(self.sp.decisions()), 2)

    def test_overwrite(self) -> None:
        self.sp.set("file", "/a.py", "allow")
        self.sp.set("file", "/a.py", "deny")
        self.assertEqual(self.sp.check("file", "/a.py"), "deny")
        self.assertEqual(len(self.sp.decisions()), 1)

    def test_sticky_flag(self) -> None:
        d = self.sp.set("file", "/a.py", "allow", sticky=True)
        self.assertTrue(d.sticky)

    def test_export_empty(self) -> None:
        self.assertEqual(self.sp.export(), [])
