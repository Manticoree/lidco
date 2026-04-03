"""Tests for TenantManager (Q264)."""
from __future__ import annotations

import unittest

from lidco.tenant.manager import Tenant, TenantManager


class TestTenantDataclass(unittest.TestCase):
    def test_defaults(self):
        t = Tenant(id="a", name="x", created_at=0.0)
        self.assertTrue(t.active)
        self.assertEqual(t.config, {})
        self.assertIsNone(t.parent_id)

    def test_fields(self):
        t = Tenant(id="b", name="y", created_at=1.0, active=False, config={"k": 1}, parent_id="a")
        self.assertFalse(t.active)
        self.assertEqual(t.config["k"], 1)
        self.assertEqual(t.parent_id, "a")


class TestCreate(unittest.TestCase):
    def test_create_basic(self):
        mgr = TenantManager()
        t = mgr.create("acme")
        self.assertEqual(t.name, "acme")
        self.assertTrue(t.active)
        self.assertIsNotNone(t.id)

    def test_create_with_config(self):
        mgr = TenantManager()
        t = mgr.create("acme", config={"model": "gpt-4"})
        self.assertEqual(t.config["model"], "gpt-4")

    def test_create_with_parent(self):
        mgr = TenantManager()
        parent = mgr.create("parent")
        child = mgr.create("child", parent_id=parent.id)
        self.assertEqual(child.parent_id, parent.id)

    def test_create_invalid_parent(self):
        mgr = TenantManager()
        with self.assertRaises(ValueError):
            mgr.create("child", parent_id="nonexistent")


class TestGetAndDelete(unittest.TestCase):
    def test_get_existing(self):
        mgr = TenantManager()
        t = mgr.create("acme")
        self.assertEqual(mgr.get(t.id).name, "acme")

    def test_get_missing(self):
        mgr = TenantManager()
        self.assertIsNone(mgr.get("nope"))

    def test_delete_soft(self):
        mgr = TenantManager()
        t = mgr.create("acme")
        self.assertTrue(mgr.delete(t.id))
        self.assertFalse(mgr.get(t.id).active)

    def test_delete_missing(self):
        mgr = TenantManager()
        self.assertFalse(mgr.delete("nope"))

    def test_activate(self):
        mgr = TenantManager()
        t = mgr.create("acme")
        mgr.delete(t.id)
        self.assertTrue(mgr.activate(t.id))
        self.assertTrue(mgr.get(t.id).active)

    def test_activate_missing(self):
        mgr = TenantManager()
        self.assertFalse(mgr.activate("nope"))


class TestConfigInheritance(unittest.TestCase):
    def test_update_config_merges(self):
        mgr = TenantManager()
        t = mgr.create("acme", config={"a": 1})
        mgr.update_config(t.id, {"b": 2})
        self.assertEqual(t.config, {"a": 1, "b": 2})

    def test_update_config_missing(self):
        mgr = TenantManager()
        self.assertIsNone(mgr.update_config("nope", {}))

    def test_resolve_config_chain(self):
        mgr = TenantManager()
        p = mgr.create("parent", config={"color": "red", "size": 10})
        c = mgr.create("child", config={"color": "blue"}, parent_id=p.id)
        resolved = mgr.resolve_config(c.id)
        self.assertEqual(resolved["color"], "blue")
        self.assertEqual(resolved["size"], 10)

    def test_resolve_config_no_parent(self):
        mgr = TenantManager()
        t = mgr.create("solo", config={"x": 1})
        self.assertEqual(mgr.resolve_config(t.id), {"x": 1})

    def test_resolve_config_missing(self):
        mgr = TenantManager()
        self.assertEqual(mgr.resolve_config("nope"), {})


class TestListAndSummary(unittest.TestCase):
    def test_children(self):
        mgr = TenantManager()
        p = mgr.create("parent")
        c1 = mgr.create("c1", parent_id=p.id)
        c2 = mgr.create("c2", parent_id=p.id)
        kids = mgr.children(p.id)
        self.assertEqual(len(kids), 2)

    def test_all_tenants_excludes_inactive(self):
        mgr = TenantManager()
        t1 = mgr.create("a")
        t2 = mgr.create("b")
        mgr.delete(t2.id)
        self.assertEqual(len(mgr.all_tenants()), 1)
        self.assertEqual(len(mgr.all_tenants(include_inactive=True)), 2)

    def test_summary(self):
        mgr = TenantManager()
        mgr.create("a")
        mgr.create("b")
        s = mgr.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["active"], 2)
        self.assertEqual(s["inactive"], 0)


if __name__ == "__main__":
    unittest.main()
