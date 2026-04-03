"""Tests for lidco.permissions.trust_levels."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.permissions.trust_levels import (
    TRUST_LEVELS,
    TrustEntry,
    TrustManager,
)


class TestTrustLevels(unittest.TestCase):
    def test_levels_defined(self) -> None:
        self.assertEqual(TRUST_LEVELS["untrusted"], 0)
        self.assertEqual(TRUST_LEVELS["basic"], 1)
        self.assertEqual(TRUST_LEVELS["elevated"], 2)
        self.assertEqual(TRUST_LEVELS["admin"], 3)


class TestTrustEntry(unittest.TestCase):
    def test_defaults(self) -> None:
        e = TrustEntry(entity="user")
        self.assertEqual(e.level, 1)
        self.assertEqual(e.history_count, 0)


class TestTrustManager(unittest.TestCase):
    def setUp(self) -> None:
        self.mgr = TrustManager(decay_seconds=86400.0, auto_escalate_threshold=10)

    def test_set_and_get_level(self) -> None:
        self.mgr.set_level("alice", 2)
        self.assertEqual(self.mgr.get_level("alice"), 2)

    def test_get_level_unknown(self) -> None:
        self.assertEqual(self.mgr.get_level("nobody"), 0)

    def test_get_entry(self) -> None:
        self.mgr.set_level("alice", 2)
        entry = self.mgr.get_entry("alice")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.level, 2)

    def test_get_entry_missing(self) -> None:
        self.assertIsNone(self.mgr.get_entry("nobody"))

    def test_record_activity_new(self) -> None:
        entry = self.mgr.record_activity("bob")
        self.assertEqual(entry.level, 1)
        self.assertEqual(entry.history_count, 1)

    def test_auto_escalate(self) -> None:
        mgr = TrustManager(auto_escalate_threshold=3)
        for _ in range(3):
            mgr.record_activity("bob")
        entry = mgr.get_entry("bob")
        self.assertEqual(entry.level, 2)  # escalated from 1 to 2
        self.assertEqual(entry.history_count, 0)  # reset after escalation

    def test_no_escalate_beyond_admin(self) -> None:
        mgr = TrustManager(auto_escalate_threshold=1)
        mgr.set_level("root", 3)
        mgr.record_activity("root")
        self.assertEqual(mgr.get_entry("root").level, 3)

    def test_apply_decay(self) -> None:
        mgr = TrustManager(decay_seconds=0.01)
        mgr.set_level("alice", 2)
        time.sleep(0.02)
        result = mgr.apply_decay("alice")
        self.assertEqual(result.level, 1)

    def test_no_decay_below_zero(self) -> None:
        mgr = TrustManager(decay_seconds=0.01)
        mgr.set_level("alice", 0)
        time.sleep(0.02)
        result = mgr.apply_decay("alice")
        self.assertEqual(result.level, 0)

    def test_check_permission(self) -> None:
        self.mgr.set_level("alice", 2)
        self.assertTrue(self.mgr.check_permission("alice", 2))
        self.assertTrue(self.mgr.check_permission("alice", 1))
        self.assertFalse(self.mgr.check_permission("alice", 3))

    def test_all_entries(self) -> None:
        self.mgr.set_level("a", 1)
        self.mgr.set_level("b", 2)
        self.assertEqual(len(self.mgr.all_entries()), 2)

    def test_summary(self) -> None:
        self.mgr.set_level("a", 1)
        self.mgr.set_level("b", 1)
        self.mgr.set_level("c", 3)
        s = self.mgr.summary()
        self.assertEqual(s[1], 2)
        self.assertEqual(s[3], 1)
