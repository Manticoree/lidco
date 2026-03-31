"""Tests for SessionRepairer."""
from __future__ import annotations

import unittest

from lidco.resilience.session_repairer import SessionRepairer, RepairResult, RepairAction


class TestSessionRepairer(unittest.TestCase):
    def setUp(self):
        self.repairer = SessionRepairer()

    # --- repair missing fields ---
    def test_repair_adds_missing_session_id(self):
        data = {}
        result = self.repairer.repair(data)
        self.assertTrue(result.repaired)
        self.assertEqual(data["session_id"], "")

    def test_repair_adds_missing_created_at(self):
        data = {}
        self.repairer.repair(data)
        self.assertEqual(data["created_at"], 0.0)

    def test_repair_adds_missing_messages(self):
        data = {}
        self.repairer.repair(data)
        self.assertEqual(data["messages"], [])

    def test_repair_adds_missing_status(self):
        data = {}
        self.repairer.repair(data)
        self.assertEqual(data["status"], "unknown")

    def test_repair_returns_actions(self):
        data = {}
        result = self.repairer.repair(data)
        self.assertGreater(len(result.actions), 0)

    # --- repair None values ---
    def test_repair_replaces_none_session_id(self):
        data = {"session_id": None, "created_at": 1.0, "messages": [], "status": "ok"}
        result = self.repairer.repair(data)
        self.assertTrue(result.repaired)
        self.assertEqual(data["session_id"], "")

    def test_repair_replaces_none_messages(self):
        data = {"session_id": "s1", "created_at": 1.0, "messages": None, "status": "ok"}
        self.repairer.repair(data)
        self.assertEqual(data["messages"], [])

    # --- type coercion ---
    def test_repair_coerces_created_at_to_float(self):
        data = {"session_id": "s1", "created_at": 42, "messages": [], "status": "ok"}
        result = self.repairer.repair(data)
        self.assertIsInstance(data["created_at"], float)
        self.assertTrue(result.repaired)

    def test_repair_coerces_session_id_to_str(self):
        data = {"session_id": 123, "created_at": 1.0, "messages": [], "status": "ok"}
        self.repairer.repair(data)
        self.assertEqual(data["session_id"], "123")

    def test_repair_no_action_on_valid_data(self):
        data = {"session_id": "s1", "created_at": 1.0, "messages": [], "status": "ok"}
        result = self.repairer.repair(data)
        self.assertFalse(result.repaired)
        self.assertEqual(len(result.actions), 0)

    # --- validate ---
    def test_validate_empty_dict(self):
        errors = self.repairer.validate({})
        self.assertGreater(len(errors), 0)

    def test_validate_valid_data(self):
        data = {"session_id": "s1", "created_at": 1.0, "messages": [], "status": "ok"}
        errors = self.repairer.validate(data)
        self.assertEqual(errors, [])

    def test_validate_wrong_type(self):
        data = {"session_id": 123, "created_at": 1.0, "messages": [], "status": "ok"}
        errors = self.repairer.validate(data)
        self.assertTrue(any("invalid type" in e for e in errors))

    def test_validate_none_field(self):
        data = {"session_id": None, "created_at": 1.0, "messages": [], "status": "ok"}
        errors = self.repairer.validate(data)
        self.assertTrue(any("None" in e for e in errors))

    # --- is_valid ---
    def test_is_valid_true(self):
        data = {"session_id": "s1", "created_at": 1.0, "messages": [], "status": "ok"}
        self.assertTrue(self.repairer.is_valid(data))

    def test_is_valid_false_missing(self):
        self.assertFalse(self.repairer.is_valid({}))

    # --- custom rules ---
    def test_add_rule_applies(self):
        self.repairer.add_rule(
            "priority",
            lambda v: isinstance(v, int) and v > 0,
            lambda v: 1,
        )
        data = {"session_id": "s1", "created_at": 1.0, "messages": [], "status": "ok", "priority": -5}
        result = self.repairer.repair(data)
        self.assertEqual(data["priority"], 1)
        self.assertTrue(result.repaired)

    def test_add_rule_validate(self):
        self.repairer.add_rule(
            "priority",
            lambda v: isinstance(v, int) and v > 0,
            lambda v: 1,
        )
        data = {"session_id": "s1", "created_at": 1.0, "messages": [], "status": "ok", "priority": -5}
        errors = self.repairer.validate(data)
        self.assertTrue(any("priority" in e for e in errors))

    def test_custom_rule_skipped_when_valid(self):
        self.repairer.add_rule(
            "priority",
            lambda v: isinstance(v, int) and v > 0,
            lambda v: 1,
        )
        data = {"session_id": "s1", "created_at": 1.0, "messages": [], "status": "ok", "priority": 5}
        result = self.repairer.repair(data)
        self.assertFalse(result.repaired)


if __name__ == "__main__":
    unittest.main()
