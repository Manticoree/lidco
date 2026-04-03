"""Tests for lidco.permissions.escalation."""
from __future__ import annotations

import time
import unittest

from lidco.permissions.escalation import (
    EscalationGrant,
    EscalationManager,
    EscalationRequest,
)


class TestEscalationRequest(unittest.TestCase):
    def test_frozen(self) -> None:
        req = EscalationRequest(
            id="abc", scope="file", resource="/a.py",
            reason="need it", requested_at=time.time(),
        )
        with self.assertRaises(AttributeError):
            req.scope = "dir"  # type: ignore[misc]

    def test_defaults(self) -> None:
        req = EscalationRequest(
            id="x", scope="tool", resource="grep",
            reason="r", requested_at=1.0,
        )
        self.assertEqual(req.ttl, 300.0)
        self.assertEqual(req.status, "pending")


class TestEscalationGrant(unittest.TestCase):
    def test_frozen(self) -> None:
        g = EscalationGrant(
            request_id="r", granted_at=1.0,
            expires_at=301.0, scope="file", resource="/b.py",
        )
        with self.assertRaises(AttributeError):
            g.scope = "dir"  # type: ignore[misc]


class TestEscalationManager(unittest.TestCase):
    def setUp(self) -> None:
        self.mgr = EscalationManager(default_ttl=300.0)

    def test_request_creates_pending(self) -> None:
        req = self.mgr.request("file", "/a.py", "testing")
        self.assertEqual(req.status, "pending")
        self.assertEqual(req.scope, "file")

    def test_approve(self) -> None:
        req = self.mgr.request("file", "/a.py", "testing")
        grant = self.mgr.approve(req.id)
        self.assertIsInstance(grant, EscalationGrant)
        self.assertEqual(grant.scope, "file")
        self.assertGreater(grant.expires_at, grant.granted_at)
        # Request status updated
        self.assertEqual(self.mgr._requests[req.id].status, "approved")

    def test_deny(self) -> None:
        req = self.mgr.request("dir", "/src", "cleanup")
        denied = self.mgr.deny(req.id)
        self.assertEqual(denied.status, "denied")

    def test_approve_nonexistent_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.mgr.approve("no-such-id")

    def test_deny_already_approved_raises(self) -> None:
        req = self.mgr.request("file", "/a.py", "reason")
        self.mgr.approve(req.id)
        with self.assertRaises(ValueError):
            self.mgr.deny(req.id)

    def test_check_active_grant(self) -> None:
        req = self.mgr.request("tool", "exec", "run it")
        self.mgr.approve(req.id)
        self.assertTrue(self.mgr.check("tool", "exec"))

    def test_check_no_grant(self) -> None:
        self.assertFalse(self.mgr.check("tool", "exec"))

    def test_revoke(self) -> None:
        req = self.mgr.request("file", "/a.py", "reason")
        self.mgr.approve(req.id)
        self.assertTrue(self.mgr.revoke(req.id))
        self.assertFalse(self.mgr.check("file", "/a.py"))

    def test_revoke_nonexistent(self) -> None:
        self.assertFalse(self.mgr.revoke("nope"))

    def test_active_grants(self) -> None:
        r1 = self.mgr.request("file", "/a.py", "reason")
        r2 = self.mgr.request("dir", "/src", "reason")
        self.mgr.approve(r1.id)
        self.mgr.approve(r2.id)
        self.assertEqual(len(self.mgr.active_grants()), 2)

    def test_cleanup_expired(self) -> None:
        mgr = EscalationManager(default_ttl=0.01)
        req = mgr.request("file", "/a.py", "testing", ttl=0.01)
        mgr.approve(req.id)
        time.sleep(0.02)
        removed = mgr.cleanup_expired()
        self.assertEqual(removed, 1)
        self.assertEqual(len(mgr.active_grants()), 0)
        self.assertEqual(mgr._requests[req.id].status, "expired")

    def test_custom_ttl(self) -> None:
        req = self.mgr.request("file", "/a.py", "reason", ttl=60.0)
        self.assertEqual(req.ttl, 60.0)

    def test_check_expired_grant_returns_false(self) -> None:
        mgr = EscalationManager(default_ttl=0.01)
        req = mgr.request("file", "/x.py", "testing", ttl=0.01)
        mgr.approve(req.id)
        time.sleep(0.02)
        self.assertFalse(mgr.check("file", "/x.py"))
