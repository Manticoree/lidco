"""Tests for AuditEventStore."""
from __future__ import annotations

import json
import time
import unittest
from dataclasses import replace

from lidco.audit.event_store import AuditEvent, AuditEventStore, _compute_checksum


class TestAuditEventStore(unittest.TestCase):
    def setUp(self):
        self.store = AuditEventStore(max_events=100)

    def test_append_returns_event(self):
        ev = self.store.append("auth", "alice", "login", "/session")
        self.assertIsInstance(ev, AuditEvent)
        self.assertEqual(ev.event_type, "auth")
        self.assertEqual(ev.actor, "alice")
        self.assertEqual(ev.action, "login")
        self.assertEqual(ev.resource, "/session")
        self.assertNotEqual(ev.checksum, "")

    def test_append_with_metadata(self):
        ev = self.store.append("auth", "alice", "login", "/session", metadata={"ip": "1.2.3.4"})
        self.assertEqual(ev.metadata, {"ip": "1.2.3.4"})

    def test_get_by_id(self):
        ev = self.store.append("auth", "alice", "login", "/session")
        found = self.store.get(ev.id)
        self.assertIs(found, ev)

    def test_get_missing(self):
        self.assertIsNone(self.store.get("nonexistent"))

    def test_count(self):
        self.assertEqual(self.store.count(), 0)
        self.store.append("auth", "alice", "login", "/session")
        self.assertEqual(self.store.count(), 1)

    def test_events_returns_copy(self):
        self.store.append("auth", "alice", "login", "/session")
        events = self.store.events()
        events.clear()
        self.assertEqual(self.store.count(), 1)

    def test_verify_valid(self):
        ev = self.store.append("auth", "alice", "login", "/session")
        self.assertTrue(self.store.verify(ev))

    def test_verify_tampered(self):
        ev = self.store.append("auth", "alice", "login", "/session")
        tampered = replace(ev, actor="mallory")
        self.assertFalse(self.store.verify(tampered))

    def test_verify_all(self):
        self.store.append("auth", "alice", "login", "/session")
        self.store.append("auth", "bob", "login", "/session")
        valid, invalid = self.store.verify_all()
        self.assertEqual(valid, 2)
        self.assertEqual(invalid, 0)

    def test_export_json(self):
        self.store.append("auth", "alice", "login", "/session")
        data = json.loads(self.store.export("json"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["actor"], "alice")

    def test_export_csv(self):
        self.store.append("auth", "alice", "login", "/session")
        csv_str = self.store.export("csv")
        self.assertIn("alice", csv_str)
        self.assertIn("event_type", csv_str)

    def test_clear_all(self):
        self.store.append("auth", "alice", "login", "/session")
        self.store.append("auth", "bob", "login", "/session")
        removed = self.store.clear()
        self.assertEqual(removed, 2)
        self.assertEqual(self.store.count(), 0)

    def test_clear_older_than(self):
        self.store.append("auth", "alice", "login", "/session")
        cutoff = time.time() + 1
        self.store.append("auth", "bob", "login", "/session")
        # Both events are before cutoff+2
        removed = self.store.clear(older_than=cutoff)
        self.assertGreaterEqual(removed, 1)

    def test_max_events_enforced(self):
        store = AuditEventStore(max_events=5)
        for i in range(10):
            store.append("test", f"actor{i}", "act", "res")
        self.assertEqual(store.count(), 5)

    def test_summary(self):
        self.store.append("auth", "alice", "login", "/session")
        self.store.append("data", "bob", "read", "/file")
        s = self.store.summary()
        self.assertEqual(s["total_events"], 2)
        self.assertEqual(s["unique_actors"], 2)
        self.assertEqual(s["unique_actions"], 2)

    def test_frozen_event(self):
        ev = self.store.append("auth", "alice", "login", "/session")
        with self.assertRaises(AttributeError):
            ev.actor = "mallory"  # type: ignore[misc]


class TestComputeChecksum(unittest.TestCase):
    def test_deterministic(self):
        c1 = _compute_checksum("t", "a", "act", "r", 1000.0)
        c2 = _compute_checksum("t", "a", "act", "r", 1000.0)
        self.assertEqual(c1, c2)

    def test_different_inputs(self):
        c1 = _compute_checksum("t", "a", "act", "r", 1000.0)
        c2 = _compute_checksum("t", "b", "act", "r", 1000.0)
        self.assertNotEqual(c1, c2)
