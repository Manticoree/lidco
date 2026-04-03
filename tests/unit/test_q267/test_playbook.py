"""Tests for lidco.incident.playbook."""
from __future__ import annotations

import unittest

from lidco.incident.detector import Incident
from lidco.incident.playbook import PlaybookResult, PlaybookStep, ResponsePlaybook


def _make_incident(itype: str = "brute_force") -> Incident:
    return Incident(id="inc1", type=itype, severity="high", description="test", actor="bot", timestamp=1.0)


class TestPlaybookStep(unittest.TestCase):
    def test_frozen(self) -> None:
        step = PlaybookStep(name="s1", action="block", target="fw")
        with self.assertRaises(AttributeError):
            step.action = "x"  # type: ignore[misc]

    def test_default_params(self) -> None:
        step = PlaybookStep(name="s1", action="block", target="fw")
        self.assertEqual(step.params, {})


class TestResponsePlaybook(unittest.TestCase):
    def setUp(self) -> None:
        self.pb = ResponsePlaybook()
        self.pb.register("brute_force", [
            PlaybookStep("block", "block", "firewall"),
            PlaybookStep("notify", "notify", "admin"),
        ])

    def test_register_and_get(self) -> None:
        steps = self.pb.get_playbook("brute_force")
        self.assertIsNotNone(steps)
        self.assertEqual(len(steps), 2)

    def test_get_nonexistent(self) -> None:
        self.assertIsNone(self.pb.get_playbook("unknown"))

    def test_execute(self) -> None:
        inc = _make_incident()
        result = self.pb.execute(inc)
        self.assertEqual(result.incident_id, "inc1")
        self.assertEqual(result.steps_executed, 2)
        self.assertEqual(result.steps_failed, 0)
        self.assertEqual(len(result.actions_taken), 2)

    def test_execute_no_playbook(self) -> None:
        inc = _make_incident("unknown_type")
        result = self.pb.execute(inc)
        self.assertEqual(result.steps_executed, 0)

    def test_playbook_types(self) -> None:
        self.assertIn("brute_force", self.pb.playbook_types())

    def test_history(self) -> None:
        self.assertEqual(len(self.pb.history()), 0)
        self.pb.execute(_make_incident())
        self.assertEqual(len(self.pb.history()), 1)

    def test_summary(self) -> None:
        s = self.pb.summary()
        self.assertEqual(s["registered_playbooks"], 1)
        self.assertEqual(s["total_executions"], 0)

    def test_result_frozen(self) -> None:
        r = PlaybookResult(incident_id="x", steps_executed=1, steps_failed=0, actions_taken=[], timestamp=0.0)
        with self.assertRaises(AttributeError):
            r.incident_id = "y"  # type: ignore[misc]

    def test_multiple_executions(self) -> None:
        self.pb.execute(_make_incident())
        self.pb.execute(_make_incident())
        self.assertEqual(len(self.pb.history()), 2)

    def test_actions_taken_format(self) -> None:
        result = self.pb.execute(_make_incident())
        self.assertEqual(result.actions_taken[0], "block:firewall")


if __name__ == "__main__":
    unittest.main()
