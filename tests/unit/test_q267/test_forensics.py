"""Tests for lidco.incident.forensics."""
from __future__ import annotations

import json
import unittest

from lidco.incident.forensics import Evidence, ForensicsCollector


class TestEvidence(unittest.TestCase):
    def test_frozen(self) -> None:
        ev = Evidence(id="e1", incident_id="i1", type="log", content="data", collected_at=1.0)
        with self.assertRaises(AttributeError):
            ev.content = "x"  # type: ignore[misc]

    def test_default_collector(self) -> None:
        ev = Evidence(id="e1", incident_id="i1", type="log", content="data", collected_at=1.0)
        self.assertEqual(ev.collector, "system")


class TestForensicsCollector(unittest.TestCase):
    def setUp(self) -> None:
        self.fc = ForensicsCollector()

    def test_collect(self) -> None:
        ev = self.fc.collect("inc1", "log", "login attempt from 10.0.0.1")
        self.assertEqual(ev.incident_id, "inc1")
        self.assertEqual(ev.type, "log")
        self.assertEqual(len(self.fc.all_evidence()), 1)

    def test_collect_custom_collector(self) -> None:
        ev = self.fc.collect("inc1", "log", "data", collector="analyst")
        self.assertEqual(ev.collector, "analyst")

    def test_get_evidence(self) -> None:
        self.fc.collect("inc1", "log", "a")
        self.fc.collect("inc2", "log", "b")
        self.assertEqual(len(self.fc.get_evidence("inc1")), 1)

    def test_timeline_sorted(self) -> None:
        # Collect multiple items — they all get time.time() so order matches insertion
        self.fc.collect("inc1", "log", "first")
        self.fc.collect("inc1", "file_change", "second")
        tl = self.fc.timeline("inc1")
        self.assertEqual(len(tl), 2)
        self.assertLessEqual(tl[0].collected_at, tl[1].collected_at)

    def test_export_json(self) -> None:
        self.fc.collect("inc1", "log", "data")
        out = self.fc.export("inc1", format="json")
        parsed = json.loads(out)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["type"], "log")

    def test_export_text(self) -> None:
        self.fc.collect("inc1", "log", "hello")
        out = self.fc.export("inc1", format="text")
        self.assertIn("[log]", out)

    def test_chain_of_custody(self) -> None:
        ev = self.fc.collect("inc1", "log", "data", collector="admin")
        chain = self.fc.chain_of_custody(ev.id)
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0]["by"], "admin")

    def test_chain_of_custody_unknown(self) -> None:
        self.assertEqual(self.fc.chain_of_custody("nonexistent"), [])

    def test_all_evidence(self) -> None:
        self.fc.collect("inc1", "log", "a")
        self.fc.collect("inc1", "api_call", "b")
        self.assertEqual(len(self.fc.all_evidence()), 2)

    def test_summary(self) -> None:
        self.fc.collect("inc1", "log", "a")
        self.fc.collect("inc2", "session", "b")
        s = self.fc.summary()
        self.assertEqual(s["total_evidence"], 2)
        self.assertEqual(s["incidents_covered"], 2)
        self.assertIn("log", s["by_type"])


if __name__ == "__main__":
    unittest.main()
