"""Tests for lidco.incident.detector."""
from __future__ import annotations

import unittest

from lidco.incident.detector import Incident, IncidentDetector


class TestIncident(unittest.TestCase):
    def test_frozen(self) -> None:
        inc = Incident(id="x", type="brute_force", severity="high", description="d", actor="a", timestamp=0.0)
        with self.assertRaises(AttributeError):
            inc.type = "other"  # type: ignore[misc]

    def test_default_indicators(self) -> None:
        inc = Incident(id="x", type="brute_force", severity="high", description="d", actor="a", timestamp=0.0)
        self.assertEqual(inc.indicators, [])

    def test_custom_indicators(self) -> None:
        inc = Incident(id="x", type="brute_force", severity="high", description="d", actor="a", timestamp=0.0, indicators=["ip=1.2.3.4"])
        self.assertEqual(inc.indicators, ["ip=1.2.3.4"])


class TestIncidentDetector(unittest.TestCase):
    def setUp(self) -> None:
        self.det = IncidentDetector()

    def test_detect_exfiltration(self) -> None:
        events = [
            {"type": "data_transfer", "actor": "user1", "bytes": 200},
        ]
        found = self.det.detect_exfiltration(events, threshold=100)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].type, "data_exfiltration")
        self.assertEqual(found[0].severity, "critical")

    def test_exfiltration_below_threshold(self) -> None:
        events = [{"type": "data_transfer", "actor": "user1", "bytes": 50}]
        found = self.det.detect_exfiltration(events, threshold=100)
        self.assertEqual(len(found), 0)

    def test_detect_brute_force(self) -> None:
        events = [{"type": "auth_failure", "actor": "bot"} for _ in range(15)]
        found = self.det.detect_brute_force(events, threshold=10)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].type, "brute_force")

    def test_brute_force_below_threshold(self) -> None:
        events = [{"type": "auth_failure", "actor": "bot"} for _ in range(3)]
        found = self.det.detect_brute_force(events, threshold=10)
        self.assertEqual(len(found), 0)

    def test_detect_policy_violation(self) -> None:
        events = [{"type": "action", "actor": "admin", "policy": "no_root_access"}]
        found = self.det.detect_policy_violation(events)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].type, "policy_violation")

    def test_analyze_events_comprehensive(self) -> None:
        events = [
            {"type": "data_transfer", "actor": "hacker", "bytes": 500},
            {"type": "auth_failure", "actor": "bot"},
        ] * 12
        found = self.det.analyze_events(events)
        types = {i.type for i in found}
        self.assertIn("data_exfiltration", types)
        self.assertIn("brute_force", types)

    def test_incidents_property(self) -> None:
        self.assertEqual(self.det.incidents(), [])
        self.det.detect_exfiltration([{"type": "data_transfer", "actor": "u", "bytes": 999}], threshold=1)
        self.assertEqual(len(self.det.incidents()), 1)

    def test_by_severity(self) -> None:
        self.det.detect_exfiltration([{"type": "data_transfer", "actor": "u", "bytes": 999}], threshold=1)
        self.assertEqual(len(self.det.by_severity("critical")), 1)
        self.assertEqual(len(self.det.by_severity("low")), 0)

    def test_summary(self) -> None:
        self.det.detect_exfiltration([{"type": "data_transfer", "actor": "u", "bytes": 999}], threshold=1)
        s = self.det.summary()
        self.assertEqual(s["total"], 1)
        self.assertIn("by_type", s)
        self.assertIn("by_severity", s)

    def test_thresholds_from_init(self) -> None:
        det = IncidentDetector(thresholds={"exfiltration": 50, "brute_force": 5})
        events = [{"type": "data_transfer", "actor": "u", "bytes": 60}]
        found = det.detect_exfiltration(events)
        self.assertEqual(len(found), 1)

    def test_anomalous_access(self) -> None:
        events = [
            {"type": "access", "actor": "stranger", "resource": "/admin"},
        ]
        found = self.det.analyze_events(events)
        types = {i.type for i in found}
        self.assertIn("anomalous_access", types)


if __name__ == "__main__":
    unittest.main()
