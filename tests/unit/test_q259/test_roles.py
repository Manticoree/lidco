"""Tests for RoleRegistry (Q259)."""
from __future__ import annotations

import unittest

from lidco.rbac.roles import Permission, Role, RoleRegistry


class TestPermission(unittest.TestCase):
    def test_frozen(self):
        p = Permission("read", "file", "Read files")
        with self.assertRaises(AttributeError):
            p.name = "write"  # type: ignore[misc]

    def test_fields(self):
        p = Permission("tool.use", "tool")
        self.assertEqual(p.name, "tool.use")
        self.assertEqual(p.scope, "tool")
        self.assertEqual(p.description, "")


class TestRole(unittest.TestCase):
    def test_defaults(self):
        r = Role(name="custom")
        self.assertEqual(r.permissions, [])
        self.assertEqual(r.inherits, [])
        self.assertEqual(r.description, "")

    def test_with_permissions(self):
        p = Permission("x", "all")
        r = Role(name="test", permissions=[p])
        self.assertEqual(len(r.permissions), 1)


class TestRoleRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = RoleRegistry()

    def test_builtin_roles_exist(self):
        for name in ("admin", "developer", "viewer", "auditor"):
            self.assertIsNotNone(self.reg.get(name))

    def test_all_roles_returns_builtins(self):
        names = {r.name for r in self.reg.all_roles()}
        self.assertIn("admin", names)
        self.assertIn("developer", names)
        self.assertIn("viewer", names)
        self.assertIn("auditor", names)

    def test_register_custom_role(self):
        role = self.reg.register(Role(name="qa", description="QA team"))
        self.assertEqual(role.name, "qa")
        self.assertIsNotNone(self.reg.get("qa"))

    def test_remove_custom_role(self):
        self.reg.register(Role(name="temp"))
        self.assertTrue(self.reg.remove("temp"))
        self.assertIsNone(self.reg.get("temp"))

    def test_cannot_remove_builtin(self):
        self.assertFalse(self.reg.remove("admin"))
        self.assertIsNotNone(self.reg.get("admin"))

    def test_remove_nonexistent(self):
        self.assertFalse(self.reg.remove("doesnotexist"))

    def test_admin_has_wildcard(self):
        perms = self.reg.resolve_permissions("admin")
        self.assertIn("*", perms)

    def test_developer_permissions(self):
        perms = self.reg.resolve_permissions("developer")
        self.assertIn("tool.use", perms)
        self.assertIn("file.read", perms)
        self.assertIn("file.write", perms)
        self.assertIn("command.execute", perms)

    def test_auditor_inherits_viewer(self):
        perms = self.reg.resolve_permissions("auditor")
        self.assertIn("read", perms)
        self.assertIn("audit.view", perms)

    def test_has_permission_admin_all(self):
        self.assertTrue(self.reg.has_permission("admin", "anything"))

    def test_has_permission_viewer_limited(self):
        self.assertTrue(self.reg.has_permission("viewer", "read"))
        self.assertFalse(self.reg.has_permission("viewer", "tool.use"))

    def test_resolve_unknown_role(self):
        perms = self.reg.resolve_permissions("ghost")
        self.assertEqual(perms, set())

    def test_summary(self):
        s = self.reg.summary()
        self.assertEqual(s["total_roles"], 4)
        self.assertIn("admin", s["builtin"])
        self.assertEqual(s["custom"], [])

    def test_summary_with_custom(self):
        self.reg.register(Role(name="custom1"))
        s = self.reg.summary()
        self.assertIn("custom1", s["custom"])


if __name__ == "__main__":
    unittest.main()
