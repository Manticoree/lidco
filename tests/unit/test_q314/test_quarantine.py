"""Tests for lidco.flaky.quarantine — FlakyQuarantine."""

from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from lidco.flaky.quarantine import (
    FlakyQuarantine,
    QuarantineEntry,
    QuarantineStatus,
    QuarantineSummary,
)


class TestQuarantineStatus(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(QuarantineStatus.ACTIVE.value, "active")
        self.assertEqual(QuarantineStatus.RELEASED.value, "released")
        self.assertEqual(QuarantineStatus.EXPIRED.value, "expired")
        self.assertEqual(QuarantineStatus.MANUAL_OVERRIDE.value, "manual_override")


class TestQuarantineEntry(unittest.TestCase):
    def test_defaults(self) -> None:
        e = QuarantineEntry(test_name="t")
        self.assertEqual(e.status, QuarantineStatus.ACTIVE)
        self.assertEqual(e.reason, "")
        self.assertEqual(e.consecutive_passes, 0)
        self.assertEqual(e.tags, [])


class TestFlakyQuarantine(unittest.TestCase):
    def test_quarantine_and_is_quarantined(self) -> None:
        q = FlakyQuarantine()
        q.quarantine("test_a", reason="flaky")
        self.assertTrue(q.is_quarantined("test_a"))
        self.assertFalse(q.is_quarantined("test_b"))

    def test_release(self) -> None:
        q = FlakyQuarantine()
        q.quarantine("test_a")
        entry = q.release("test_a")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.status, QuarantineStatus.RELEASED)
        self.assertFalse(q.is_quarantined("test_a"))

    def test_release_nonexistent(self) -> None:
        q = FlakyQuarantine()
        self.assertIsNone(q.release("nope"))

    def test_override(self) -> None:
        q = FlakyQuarantine()
        q.quarantine("test_a")
        entry = q.override("test_a")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.status, QuarantineStatus.MANUAL_OVERRIDE)
        self.assertFalse(q.is_quarantined("test_a"))

    def test_override_nonexistent(self) -> None:
        q = FlakyQuarantine()
        self.assertIsNone(q.override("nope"))

    def test_record_pass_auto_release(self) -> None:
        q = FlakyQuarantine(passes_to_release=2)
        q.quarantine("test_a")
        q.record_pass("test_a")
        self.assertTrue(q.is_quarantined("test_a"))
        q.record_pass("test_a")
        entry = q.get_entry("test_a")
        self.assertEqual(entry.status, QuarantineStatus.RELEASED)

    def test_record_fail_resets_passes(self) -> None:
        q = FlakyQuarantine(passes_to_release=3)
        q.quarantine("test_a")
        q.record_pass("test_a")
        q.record_pass("test_a")
        q.record_fail("test_a")
        entry = q.get_entry("test_a")
        self.assertEqual(entry.consecutive_passes, 0)
        self.assertTrue(q.is_quarantined("test_a"))

    def test_record_pass_nonexistent(self) -> None:
        q = FlakyQuarantine()
        self.assertIsNone(q.record_pass("nope"))

    def test_record_fail_nonexistent(self) -> None:
        q = FlakyQuarantine()
        self.assertIsNone(q.record_fail("nope"))

    def test_get_entry(self) -> None:
        q = FlakyQuarantine()
        q.quarantine("test_a", reason="flaky", tags=["ci"])
        entry = q.get_entry("test_a")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.reason, "flaky")
        self.assertEqual(entry.tags, ["ci"])

    def test_get_entry_nonexistent(self) -> None:
        q = FlakyQuarantine()
        self.assertIsNone(q.get_entry("nope"))

    def test_summary(self) -> None:
        q = FlakyQuarantine()
        q.quarantine("a")
        q.quarantine("b")
        q.release("b")
        s = q.summary()
        self.assertEqual(s.total, 2)
        self.assertEqual(s.active, 1)
        self.assertEqual(s.released, 1)

    def test_expiration(self) -> None:
        q = FlakyQuarantine(default_ttl_seconds=0.01)
        q.quarantine("test_a")
        time.sleep(0.05)
        self.assertFalse(q.is_quarantined("test_a"))
        entry = q.get_entry("test_a")
        self.assertEqual(entry.status, QuarantineStatus.EXPIRED)

    def test_listener_called(self) -> None:
        events: list[tuple[str, str]] = []
        q = FlakyQuarantine()
        q.add_listener(lambda evt, e: events.append((evt, e.test_name)))
        q.quarantine("test_a")
        q.release("test_a")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], ("quarantined", "test_a"))
        self.assertEqual(events[1], ("released", "test_a"))

    def test_listener_exception_swallowed(self) -> None:
        def bad_listener(evt: str, e: QuarantineEntry) -> None:
            raise RuntimeError("boom")

        q = FlakyQuarantine()
        q.add_listener(bad_listener)
        # Should not raise
        q.quarantine("test_a")
        self.assertTrue(q.is_quarantined("test_a"))

    def test_passes_to_release_at_least_one(self) -> None:
        q = FlakyQuarantine(passes_to_release=0)
        self.assertEqual(q._passes_to_release, 1)

    def test_persistence_save_load(self, tmp_path: Path | None = None) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "quarantine.json"
            q1 = FlakyQuarantine(store_path=p)
            q1.quarantine("test_a", reason="flaky", tags=["ci"])
            q1.quarantine("test_b")
            q1.release("test_b")

            # Load from file
            q2 = FlakyQuarantine(store_path=p)
            self.assertTrue(q2.is_quarantined("test_a"))
            entry = q2.get_entry("test_a")
            self.assertEqual(entry.reason, "flaky")
            self.assertEqual(entry.tags, ["ci"])
            b = q2.get_entry("test_b")
            self.assertEqual(b.status, QuarantineStatus.RELEASED)

    def test_persistence_corrupt_json(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "quarantine.json"
            p.write_text("not json")
            q = FlakyQuarantine(store_path=p)
            self.assertEqual(q.summary().total, 0)

    def test_auto_release_notification(self) -> None:
        events: list[str] = []
        q = FlakyQuarantine(passes_to_release=1)
        q.add_listener(lambda evt, e: events.append(evt))
        q.quarantine("t")
        q.record_pass("t")
        self.assertIn("auto_released", events)

    def test_custom_ttl(self) -> None:
        q = FlakyQuarantine()
        entry = q.quarantine("t", ttl_seconds=100.0)
        self.assertGreater(entry.release_after, entry.quarantined_at)
        diff = entry.release_after - entry.quarantined_at
        self.assertAlmostEqual(diff, 100.0, places=0)


class TestQuarantineSummary(unittest.TestCase):
    def test_defaults(self) -> None:
        s = QuarantineSummary(total=0, active=0, released=0, expired=0, overridden=0)
        self.assertEqual(s.entries, [])


if __name__ == "__main__":
    unittest.main()
