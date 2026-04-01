"""Tests for budget.tool_gate — ToolBudgetGate."""
from __future__ import annotations

import unittest

from lidco.budget.tool_gate import GateDecision, GateResult, ToolBudgetGate


class TestGateDecision(unittest.TestCase):
    def test_values(self):
        self.assertEqual(GateDecision.ALLOW, "ALLOW")
        self.assertEqual(GateDecision.WARN, "WARN")
        self.assertEqual(GateDecision.DENY, "DENY")
        self.assertEqual(GateDecision.OVERRIDE, "OVERRIDE")


class TestGateResult(unittest.TestCase):
    def test_frozen(self):
        r = GateResult(decision=GateDecision.ALLOW, tool_name="Read")
        with self.assertRaises(AttributeError):
            r.decision = GateDecision.DENY  # type: ignore[misc]

    def test_defaults(self):
        r = GateResult(decision=GateDecision.ALLOW, tool_name="x")
        self.assertEqual(r.estimated_tokens, 0)
        self.assertEqual(r.budget_remaining, 0)
        self.assertEqual(r.message, "")


class TestToolBudgetGate(unittest.TestCase):
    def test_allow_within_budget(self):
        gate = ToolBudgetGate(budget_remaining=10_000, warn_threshold=2_000)
        result = gate.check("Grep", 500)
        self.assertEqual(result.decision, GateDecision.ALLOW)

    def test_warn_low_budget(self):
        gate = ToolBudgetGate(budget_remaining=3_000, warn_threshold=5_000)
        result = gate.check("Grep", 100)
        self.assertEqual(result.decision, GateDecision.WARN)
        self.assertIn("low", result.message)

    def test_deny_over_budget(self):
        gate = ToolBudgetGate(budget_remaining=100, warn_threshold=50)
        result = gate.check("Grep", 500)
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertEqual(gate.get_denied_count(), 1)

    def test_override_critical_over_budget(self):
        gate = ToolBudgetGate(budget_remaining=10, warn_threshold=5)
        result = gate.check("Write", 1000)
        self.assertEqual(result.decision, GateDecision.OVERRIDE)
        self.assertIn("overrides", result.message)

    def test_critical_allow_within_budget(self):
        gate = ToolBudgetGate(budget_remaining=50_000)
        result = gate.check("Edit", 100)
        self.assertEqual(result.decision, GateDecision.ALLOW)

    def test_is_critical_default(self):
        gate = ToolBudgetGate()
        self.assertTrue(gate.is_critical("Write"))
        self.assertTrue(gate.is_critical("Edit"))
        self.assertFalse(gate.is_critical("Grep"))

    def test_add_critical(self):
        gate = ToolBudgetGate()
        gate.add_critical("Bash")
        self.assertTrue(gate.is_critical("Bash"))

    def test_update_budget(self):
        gate = ToolBudgetGate(budget_remaining=100)
        gate.update_budget(50_000)
        result = gate.check("Grep", 1000)
        self.assertEqual(result.decision, GateDecision.ALLOW)

    def test_denied_count_accumulates(self):
        gate = ToolBudgetGate(budget_remaining=10, warn_threshold=5)
        gate.check("Grep", 100)
        gate.check("Read", 200)
        self.assertEqual(gate.get_denied_count(), 2)

    def test_summary(self):
        gate = ToolBudgetGate(budget_remaining=5000, warn_threshold=1000)
        s = gate.summary()
        self.assertIn("5000", s)
        self.assertIn("1000", s)
        self.assertIn("Edit", s)
        self.assertIn("Write", s)

    def test_deny_does_not_count_critical(self):
        gate = ToolBudgetGate(budget_remaining=5, warn_threshold=2)
        gate.check("Write", 999)  # OVERRIDE, not DENY
        self.assertEqual(gate.get_denied_count(), 0)

    def test_multiple_critical_tools(self):
        gate = ToolBudgetGate(critical_tools=("Write", "Edit", "Bash"))
        self.assertTrue(gate.is_critical("Bash"))


if __name__ == "__main__":
    unittest.main()
