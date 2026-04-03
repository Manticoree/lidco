"""Tests for TenantRouter (Q264)."""
from __future__ import annotations

import unittest

from lidco.tenant.manager import TenantManager
from lidco.tenant.router import RouteResult, TenantRouter


class TestRouteResult(unittest.TestCase):
    def test_frozen(self):
        r = RouteResult(tenant_id="t1", session_id="s1", matched_by="session")
        with self.assertRaises(AttributeError):
            r.tenant_id = "t2"  # type: ignore[misc]

    def test_fields(self):
        r = RouteResult(tenant_id="t1", session_id=None, matched_by="default")
        self.assertEqual(r.matched_by, "default")
        self.assertIsNone(r.session_id)


class TestBindAndUnbind(unittest.TestCase):
    def setUp(self):
        self.mgr = TenantManager()
        self.t = self.mgr.create("acme")
        self.router = TenantRouter(self.mgr)

    def test_bind_valid(self):
        self.router.bind_session("s1", self.t.id)
        self.assertIn("s1", self.router.active_bindings())

    def test_bind_invalid_tenant(self):
        with self.assertRaises(ValueError):
            self.router.bind_session("s1", "nonexistent")

    def test_unbind_existing(self):
        self.router.bind_session("s1", self.t.id)
        self.assertTrue(self.router.unbind_session("s1"))

    def test_unbind_missing(self):
        self.assertFalse(self.router.unbind_session("s999"))


class TestRouting(unittest.TestCase):
    def setUp(self):
        self.mgr = TenantManager()
        self.t1 = self.mgr.create("acme")
        self.t2 = self.mgr.create("beta")
        self.router = TenantRouter(self.mgr, default_tenant=self.t1.id)

    def test_route_by_session(self):
        self.router.bind_session("s1", self.t2.id)
        r = self.router.route(session_id="s1")
        self.assertEqual(r.tenant_id, self.t2.id)
        self.assertEqual(r.matched_by, "session")

    def test_route_by_header(self):
        r = self.router.route(tenant_header=self.t2.id)
        self.assertEqual(r.tenant_id, self.t2.id)
        self.assertEqual(r.matched_by, "header")

    def test_route_by_default(self):
        r = self.router.route()
        self.assertEqual(r.tenant_id, self.t1.id)
        self.assertEqual(r.matched_by, "default")

    def test_route_no_match(self):
        router = TenantRouter(self.mgr)
        with self.assertRaises(ValueError):
            router.route()


class TestSessionsForTenant(unittest.TestCase):
    def test_sessions_for_tenant(self):
        mgr = TenantManager()
        t = mgr.create("acme")
        router = TenantRouter(mgr)
        router.bind_session("s1", t.id)
        router.bind_session("s2", t.id)
        self.assertEqual(sorted(router.sessions_for_tenant(t.id)), ["s1", "s2"])

    def test_summary(self):
        mgr = TenantManager()
        t = mgr.create("acme")
        router = TenantRouter(mgr, default_tenant=t.id)
        s = router.summary()
        self.assertEqual(s["bindings"], 0)
        self.assertEqual(s["default_tenant"], t.id)


if __name__ == "__main__":
    unittest.main()
