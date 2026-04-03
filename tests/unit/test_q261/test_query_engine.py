"""Tests for AuditQueryEngine."""
from __future__ import annotations

import json
import time
import unittest
from unittest.mock import patch

from lidco.audit.event_store import AuditEventStore
from lidco.audit.query_engine import AuditQueryEngine, QueryFilter


class TestAuditQueryEngine(unittest.TestCase):
    def setUp(self):
        self.store = AuditEventStore()
        self.engine = AuditQueryEngine(self.store)
        # Seed events with controlled timestamps
        base = 1_700_000_000.0
        with patch("lidco.audit.event_store.time.time", side_effect=[base + i * 60 for i in range(6)]):
            self.store.append("auth", "alice", "login", "/session")
            self.store.append("auth", "bob", "login", "/session")
            self.store.append("data", "alice", "read", "/file.txt")
            self.store.append("data", "alice", "write", "/file.txt")
            self.store.append("admin", "carol", "grant_admin", "/users/bob")
            self.store.append("auth", "bob", "logout", "/session")

    def test_query_all(self):
        results = self.engine.query(QueryFilter())
        self.assertEqual(len(results), 6)

    def test_query_by_actor(self):
        results = self.engine.query(QueryFilter(actor="alice"))
        self.assertEqual(len(results), 3)
        self.assertTrue(all(e.actor == "alice" for e in results))

    def test_query_by_action(self):
        results = self.engine.query(QueryFilter(action="login"))
        self.assertEqual(len(results), 2)

    def test_query_by_event_type(self):
        results = self.engine.query(QueryFilter(event_type="data"))
        self.assertEqual(len(results), 2)

    def test_query_by_resource_pattern(self):
        results = self.engine.query(QueryFilter(resource_pattern="*.txt"))
        self.assertEqual(len(results), 2)

    def test_query_with_limit_offset(self):
        results = self.engine.query(QueryFilter(), limit=2, offset=1)
        self.assertEqual(len(results), 2)

    def test_count(self):
        c = self.engine.count(QueryFilter(actor="alice"))
        self.assertEqual(c, 3)

    def test_aggregate_by_actor(self):
        agg = self.engine.aggregate_by("actor")
        self.assertEqual(agg["alice"], 3)
        self.assertEqual(agg["bob"], 2)
        self.assertEqual(agg["carol"], 1)

    def test_aggregate_by_action(self):
        agg = self.engine.aggregate_by("action")
        self.assertEqual(agg["login"], 2)

    def test_timeline(self):
        tl = self.engine.timeline(bucket_minutes=5)
        self.assertIsInstance(tl, list)
        self.assertTrue(all("bucket" in b and "count" in b for b in tl))
        total = sum(b["count"] for b in tl)
        self.assertEqual(total, 6)

    def test_actors(self):
        actors = self.engine.actors()
        self.assertIn("alice", actors)
        self.assertIn("bob", actors)
        self.assertIn("carol", actors)

    def test_actions(self):
        actions = self.engine.actions()
        self.assertIn("login", actions)
        self.assertIn("read", actions)

    def test_export_json(self):
        data = json.loads(self.engine.export(QueryFilter(actor="alice"), format="json"))
        self.assertEqual(len(data), 3)

    def test_export_csv(self):
        csv_str = self.engine.export(QueryFilter(actor="bob"), format="csv")
        self.assertIn("bob", csv_str)

    def test_timeline_empty(self):
        empty_store = AuditEventStore()
        engine = AuditQueryEngine(empty_store)
        self.assertEqual(engine.timeline(), [])
