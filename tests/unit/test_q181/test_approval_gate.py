"""Tests for ApprovalGate, ApprovalManager, and ApprovalRequest."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.templates.approval_gate import (
    ApprovalError,
    ApprovalGate,
    ApprovalManager,
    ApprovalRequest,
)


class TestApprovalGate(unittest.TestCase):
    def test_frozen(self):
        gate = ApprovalGate(name="deploy")
        with self.assertRaises(AttributeError):
            gate.name = "other"  # type: ignore[misc]

    def test_defaults(self):
        gate = ApprovalGate(name="deploy")
        self.assertEqual(gate.timeout_seconds, 300.0)
        self.assertEqual(gate.default_action, "approve")
        self.assertFalse(gate.require_reason)


class TestApprovalManagerGates(unittest.TestCase):
    def test_add_and_get_gate(self):
        mgr = ApprovalManager()
        gate = ApprovalGate(name="deploy", description="Prod deploy gate")
        mgr.add_gate(gate)
        retrieved = mgr.get_gate("deploy")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.description, "Prod deploy gate")

    def test_remove_gate(self):
        mgr = ApprovalManager()
        mgr.add_gate(ApprovalGate(name="deploy"))
        self.assertTrue(mgr.remove_gate("deploy"))
        self.assertFalse(mgr.remove_gate("deploy"))

    def test_list_gates(self):
        mgr = ApprovalManager()
        mgr.add_gate(ApprovalGate(name="a"))
        mgr.add_gate(ApprovalGate(name="b"))
        self.assertEqual(len(mgr.list_gates()), 2)


class TestApprovalManagerRequests(unittest.TestCase):
    def setUp(self):
        self.mgr = ApprovalManager()
        self.mgr.add_gate(ApprovalGate(name="deploy"))

    def test_request_approval(self):
        req = self.mgr.request_approval("deploy", "alice", {"env": "prod"})
        self.assertEqual(req.status, "pending")
        self.assertEqual(req.gate_name, "deploy")
        self.assertEqual(req.requester, "alice")
        self.assertEqual(req.context, {"env": "prod"})

    def test_request_unknown_gate_raises(self):
        with self.assertRaises(ApprovalError):
            self.mgr.request_approval("nonexistent", "alice")

    def test_approve(self):
        self.mgr.request_approval("deploy", "alice")
        req = self.mgr.approve("1", reason="LGTM")
        self.assertEqual(req.status, "approved")
        self.assertEqual(req.reason, "LGTM")
        self.assertGreater(req.resolved_at, 0)

    def test_reject(self):
        self.mgr.request_approval("deploy", "alice")
        req = self.mgr.reject("1", reason="Not ready")
        self.assertEqual(req.status, "rejected")
        self.assertEqual(req.reason, "Not ready")

    def test_approve_already_resolved_raises(self):
        self.mgr.request_approval("deploy", "alice")
        self.mgr.approve("1")
        with self.assertRaises(ApprovalError):
            self.mgr.approve("1")

    def test_reject_already_resolved_raises(self):
        self.mgr.request_approval("deploy", "alice")
        self.mgr.reject("1")
        with self.assertRaises(ApprovalError):
            self.mgr.reject("1")

    def test_get_request(self):
        self.mgr.request_approval("deploy", "alice")
        req = self.mgr.get_request("1")
        self.assertIsNotNone(req)
        self.assertIsNone(self.mgr.get_request("999"))

    def test_list_requests_filtered(self):
        self.mgr.request_approval("deploy", "alice")
        self.mgr.request_approval("deploy", "bob")
        self.mgr.approve("1")
        pending = self.mgr.list_requests(status="pending")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].requester, "bob")
        all_deploy = self.mgr.list_requests(gate_name="deploy")
        self.assertEqual(len(all_deploy), 2)


class TestApprovalManagerTimeout(unittest.TestCase):
    def test_check_timeouts_auto_approve(self):
        mgr = ApprovalManager()
        mgr.add_gate(ApprovalGate(name="deploy", timeout_seconds=0.0, default_action="approve"))
        mgr.request_approval("deploy", "alice")
        # With timeout_seconds=0.0, any elapsed time triggers timeout
        resolved = mgr.check_timeouts()
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].status, "approved")
        self.assertEqual(resolved[0].reason, "auto: timeout")

    def test_check_timeouts_auto_reject(self):
        mgr = ApprovalManager()
        mgr.add_gate(ApprovalGate(name="deploy", timeout_seconds=0.0, default_action="reject"))
        mgr.request_approval("deploy", "alice")
        resolved = mgr.check_timeouts()
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].status, "rejected")

    def test_no_timeout_when_not_expired(self):
        mgr = ApprovalManager()
        mgr.add_gate(ApprovalGate(name="deploy", timeout_seconds=9999.0))
        mgr.request_approval("deploy", "alice")
        resolved = mgr.check_timeouts()
        self.assertEqual(len(resolved), 0)


class TestApprovalManagerAuditLog(unittest.TestCase):
    def test_audit_log(self):
        mgr = ApprovalManager()
        mgr.add_gate(ApprovalGate(name="deploy"))
        mgr.request_approval("deploy", "alice")
        mgr.request_approval("deploy", "bob")
        mgr.approve("1", reason="ok")
        mgr.reject("2", reason="nope")
        log = mgr.audit_log()
        self.assertEqual(len(log), 2)
        ids = {entry["id"] for entry in log}
        self.assertEqual(ids, {"1", "2"})
        statuses = {entry["status"] for entry in log}
        self.assertEqual(statuses, {"approved", "rejected"})

    def test_audit_log_excludes_pending(self):
        mgr = ApprovalManager()
        mgr.add_gate(ApprovalGate(name="deploy"))
        mgr.request_approval("deploy", "alice")
        log = mgr.audit_log()
        self.assertEqual(len(log), 0)


class TestApprovalManagerRequireReason(unittest.TestCase):
    def test_require_reason_approve(self):
        mgr = ApprovalManager()
        mgr.add_gate(ApprovalGate(name="prod", require_reason=True))
        mgr.request_approval("prod", "alice")
        with self.assertRaises(ApprovalError):
            mgr.approve("1", reason="")
        req = mgr.approve("1", reason="Tested in staging")
        self.assertEqual(req.status, "approved")

    def test_require_reason_reject(self):
        mgr = ApprovalManager()
        mgr.add_gate(ApprovalGate(name="prod", require_reason=True))
        mgr.request_approval("prod", "alice")
        with self.assertRaises(ApprovalError):
            mgr.reject("1", reason="")
        req = mgr.reject("1", reason="Failed QA")
        self.assertEqual(req.status, "rejected")


if __name__ == "__main__":
    unittest.main()
