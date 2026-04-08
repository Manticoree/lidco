"""Tests for lidco.configmgmt.audit — Config Audit."""

from __future__ import annotations

import json
import unittest

from lidco.configmgmt.audit import (
    AuditAction,
    AuditEntry,
    ComplianceReport,
    ConfigAudit,
)


class TestConfigAudit(unittest.TestCase):
    """Tests for ConfigAudit."""

    def setUp(self) -> None:
        self.audit = ConfigAudit()

    # -- Recording ---------------------------------------------------------

    def test_record_creates_entry(self) -> None:
        entry = self.audit.record(
            AuditAction.CREATE, "alice", "app.json",
            {"host": "localhost"},
            reason="initial setup",
        )
        self.assertEqual(entry.action, AuditAction.CREATE)
        self.assertEqual(entry.user, "alice")
        self.assertEqual(entry.config_name, "app.json")
        self.assertEqual(entry.reason, "initial setup")
        self.assertIn("host", entry.snapshot)

    def test_record_stores_changes(self) -> None:
        entry = self.audit.record(
            AuditAction.UPDATE, "bob", "app.json",
            {"host": "prod"},
            changes={"host": "localhost -> prod"},
        )
        self.assertEqual(entry.changes["host"], "localhost -> prod")

    def test_record_snapshot_is_deep_copy(self) -> None:
        data = {"nested": {"key": "val"}}
        entry = self.audit.record(AuditAction.CREATE, "alice", "cfg", data)
        data["nested"]["key"] = "changed"
        self.assertEqual(entry.snapshot["nested"]["key"], "val")

    # -- Querying ----------------------------------------------------------

    def test_get_history_all(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "a", {})
        self.audit.record(AuditAction.CREATE, "bob", "b", {})
        self.assertEqual(len(self.audit.get_history()), 2)

    def test_get_history_by_config(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "a", {})
        self.audit.record(AuditAction.CREATE, "bob", "b", {})
        self.assertEqual(len(self.audit.get_history("a")), 1)

    def test_get_user_history(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "a", {})
        self.audit.record(AuditAction.CREATE, "bob", "b", {})
        self.assertEqual(len(self.audit.get_user_history("alice")), 1)

    def test_get_latest(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "a", {"v": 1})
        self.audit.record(AuditAction.UPDATE, "alice", "a", {"v": 2})
        latest = self.audit.get_latest("a")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.action, AuditAction.UPDATE)

    def test_get_latest_none(self) -> None:
        self.assertIsNone(self.audit.get_latest("nope"))

    # -- Rollback ----------------------------------------------------------

    def test_rollback(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "cfg", {"v": 1})
        self.audit.record(AuditAction.UPDATE, "alice", "cfg", {"v": 2})
        restored = self.audit.rollback("cfg", "alice", reason="revert")
        self.assertIsNotNone(restored)
        self.assertEqual(restored["v"], 1)

    def test_rollback_not_enough_snapshots(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "cfg", {"v": 1})
        result = self.audit.rollback("cfg", "alice")
        self.assertIsNone(result)

    def test_rollback_no_config(self) -> None:
        result = self.audit.rollback("missing", "alice")
        self.assertIsNone(result)

    def test_rollback_records_entry(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "cfg", {"v": 1})
        self.audit.record(AuditAction.UPDATE, "alice", "cfg", {"v": 2})
        self.audit.rollback("cfg", "alice")
        history = self.audit.get_history("cfg")
        self.assertEqual(history[-1].action, AuditAction.ROLLBACK)

    # -- Snapshots ---------------------------------------------------------

    def test_get_snapshot(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "cfg", {"v": 1})
        snap = self.audit.get_snapshot("cfg", 0)
        self.assertEqual(snap, {"v": 1})

    def test_get_snapshot_latest(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "cfg", {"v": 1})
        self.audit.record(AuditAction.UPDATE, "alice", "cfg", {"v": 2})
        snap = self.audit.get_snapshot("cfg", -1)
        self.assertEqual(snap, {"v": 2})

    def test_get_snapshot_missing(self) -> None:
        self.assertIsNone(self.audit.get_snapshot("nope"))

    def test_get_snapshot_out_of_range(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "cfg", {"v": 1})
        self.assertIsNone(self.audit.get_snapshot("cfg", 99))

    def test_snapshot_count(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "cfg", {"v": 1})
        self.audit.record(AuditAction.UPDATE, "alice", "cfg", {"v": 2})
        self.assertEqual(self.audit.snapshot_count("cfg"), 2)

    def test_snapshot_count_missing(self) -> None:
        self.assertEqual(self.audit.snapshot_count("nope"), 0)

    # -- Compliance --------------------------------------------------------

    def test_compliance_report_empty(self) -> None:
        rpt = self.audit.compliance_report()
        self.assertEqual(rpt.total_changes, 0)
        self.assertEqual(rpt.period_start, "")

    def test_compliance_report_with_data(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "a", {})
        self.audit.record(AuditAction.UPDATE, "bob", "a", {})
        rpt = self.audit.compliance_report()
        self.assertEqual(rpt.total_changes, 2)
        self.assertEqual(rpt.changes_by_user["alice"], 1)
        self.assertEqual(rpt.changes_by_user["bob"], 1)
        self.assertIn("a", rpt.configs_modified)

    def test_compliance_report_by_action(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "a", {})
        self.audit.record(AuditAction.UPDATE, "alice", "a", {})
        rpt = self.audit.compliance_report()
        self.assertEqual(rpt.changes_by_action["create"], 1)
        self.assertEqual(rpt.changes_by_action["update"], 1)

    # -- Export ------------------------------------------------------------

    def test_export_json(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "cfg", {"v": 1})
        text = self.audit.export_json()
        data = json.loads(text)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["user"], "alice")

    def test_export_json_filtered(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "a", {})
        self.audit.record(AuditAction.CREATE, "bob", "b", {})
        text = self.audit.export_json("a")
        data = json.loads(text)
        self.assertEqual(len(data), 1)

    # -- Clear -------------------------------------------------------------

    def test_clear(self) -> None:
        self.audit.record(AuditAction.CREATE, "alice", "cfg", {})
        self.audit.clear()
        self.assertEqual(len(self.audit.get_history()), 0)
        self.assertEqual(self.audit.snapshot_count("cfg"), 0)


if __name__ == "__main__":
    unittest.main()
