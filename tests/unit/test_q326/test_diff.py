"""Tests for lidco.configmgmt.diff — Config Diff."""

from __future__ import annotations

import unittest

from lidco.configmgmt.diff import (
    ApprovalRequest,
    ChangeKind,
    ConfigChange,
    ConfigDiff,
    DiffResult,
    RiskLevel,
)


class TestConfigDiff(unittest.TestCase):
    """Tests for ConfigDiff."""

    def setUp(self) -> None:
        self.differ = ConfigDiff()

    # -- Basic diffing -----------------------------------------------------

    def test_diff_identical(self) -> None:
        cfg = {"host": "localhost", "port": 5432}
        result = self.differ.diff(cfg, cfg)
        self.assertEqual(result.total_changes, 0)

    def test_diff_added_key(self) -> None:
        result = self.differ.diff({"a": 1}, {"a": 1, "b": 2})
        self.assertEqual(len(result.added), 1)
        self.assertEqual(result.added[0].path, "b")
        self.assertEqual(result.added[0].new_value, 2)

    def test_diff_removed_key(self) -> None:
        result = self.differ.diff({"a": 1, "b": 2}, {"a": 1})
        self.assertEqual(len(result.removed), 1)
        self.assertEqual(result.removed[0].path, "b")

    def test_diff_modified_key(self) -> None:
        result = self.differ.diff({"a": 1}, {"a": 2})
        self.assertEqual(len(result.modified), 1)
        self.assertEqual(result.modified[0].old_value, 1)
        self.assertEqual(result.modified[0].new_value, 2)

    def test_diff_nested(self) -> None:
        src = {"db": {"host": "localhost", "port": 5432}}
        tgt = {"db": {"host": "prod.db", "port": 5432}}
        result = self.differ.diff(src, tgt)
        self.assertEqual(len(result.modified), 1)
        self.assertEqual(result.modified[0].path, "db.host")

    def test_diff_names(self) -> None:
        result = self.differ.diff({}, {}, source_name="dev", target_name="prod")
        self.assertEqual(result.source_name, "dev")
        self.assertEqual(result.target_name, "prod")

    # -- Risk assessment ---------------------------------------------------

    def test_dangerous_key(self) -> None:
        self.differ.mark_dangerous("password")
        result = self.differ.diff({"password": "old"}, {"password": "new"})
        self.assertEqual(result.modified[0].risk, RiskLevel.HIGH)

    def test_critical_key(self) -> None:
        self.differ.mark_critical("secret")
        result = self.differ.diff({"secret": "old"}, {"secret": "new"})
        self.assertEqual(result.modified[0].risk, RiskLevel.CRITICAL)

    def test_dangerous_changes_property(self) -> None:
        self.differ.mark_dangerous("token")
        result = self.differ.diff(
            {"token": "a", "host": "x"},
            {"token": "b", "host": "y"},
        )
        self.assertEqual(len(result.dangerous_changes), 1)
        self.assertTrue(result.needs_approval)

    def test_no_dangerous_changes(self) -> None:
        result = self.differ.diff({"host": "a"}, {"host": "b"})
        self.assertEqual(len(result.dangerous_changes), 0)
        self.assertFalse(result.needs_approval)

    # -- Environment diffing -----------------------------------------------

    def test_diff_environments(self) -> None:
        configs = {
            "dev": {"host": "localhost"},
            "prod": {"host": "prod.db"},
        }
        result = self.differ.diff_environments(configs, "dev", "prod")
        self.assertEqual(result.source_name, "dev")
        self.assertEqual(result.target_name, "prod")
        self.assertEqual(len(result.modified), 1)

    def test_diff_environments_missing_base(self) -> None:
        with self.assertRaises(KeyError):
            self.differ.diff_environments({}, "dev", "prod")

    def test_diff_environments_missing_target(self) -> None:
        with self.assertRaises(KeyError):
            self.differ.diff_environments({"dev": {}}, "dev", "prod")

    # -- Approval workflow -------------------------------------------------

    def test_request_approval(self) -> None:
        result = self.differ.diff({"a": 1}, {"a": 2})
        req = self.differ.request_approval(result, requester="alice", reason="deploy")
        self.assertFalse(req.approved)
        self.assertEqual(req.requester, "alice")

    def test_approve(self) -> None:
        result = self.differ.diff({"a": 1}, {"a": 2})
        req = self.differ.request_approval(result)
        approved = self.differ.approve(req, approver="bob")
        self.assertTrue(approved.approved)
        self.assertEqual(approved.approver, "bob")

    def test_pending_approvals(self) -> None:
        result = self.differ.diff({"a": 1}, {"a": 2})
        req = self.differ.request_approval(result)
        self.assertEqual(len(self.differ.pending_approvals()), 1)
        self.differ.approve(req, "bob")
        self.assertEqual(len(self.differ.pending_approvals()), 0)

    # -- Summary -----------------------------------------------------------

    def test_summary_output(self) -> None:
        self.differ.mark_critical("secret")
        result = self.differ.diff(
            {"host": "a", "secret": "old"},
            {"host": "b", "secret": "new"},
            source_name="dev",
            target_name="prod",
        )
        text = self.differ.summary(result)
        self.assertIn("dev", text)
        self.assertIn("prod", text)
        self.assertIn("Dangerous", text)

    # -- DiffResult properties ---------------------------------------------

    def test_diff_result_total(self) -> None:
        result = DiffResult(changes=[
            ConfigChange(path="a", kind=ChangeKind.ADDED),
            ConfigChange(path="b", kind=ChangeKind.REMOVED),
        ])
        self.assertEqual(result.total_changes, 2)


if __name__ == "__main__":
    unittest.main()
