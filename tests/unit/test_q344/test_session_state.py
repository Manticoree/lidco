"""Tests for SessionStateValidator (Q344)."""
from __future__ import annotations

import time
import unittest


def _validator():
    from lidco.stability.session_state import SessionStateValidator
    return SessionStateValidator()


def _good_state(**overrides):
    state = {
        "session_id": "sess-001",
        "created_at": time.time() - 100,
        "status": "active",
    }
    state.update(overrides)
    return state


class TestValidateConsistency(unittest.TestCase):
    def test_valid_state_returns_valid_true(self):
        result = _validator().validate_consistency(_good_state())
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_missing_session_id_is_error(self):
        state = _good_state()
        del state["session_id"]
        result = _validator().validate_consistency(state)
        self.assertFalse(result["valid"])
        self.assertTrue(any("session_id" in e for e in result["errors"]))

    def test_missing_created_at_is_error(self):
        state = _good_state()
        del state["created_at"]
        result = _validator().validate_consistency(state)
        self.assertFalse(result["valid"])

    def test_empty_session_id_is_error(self):
        state = _good_state(session_id="   ")
        result = _validator().validate_consistency(state)
        self.assertFalse(result["valid"])

    def test_negative_created_at_is_error(self):
        state = _good_state(created_at=-1)
        result = _validator().validate_consistency(state)
        self.assertFalse(result["valid"])

    def test_unknown_status_is_warning_not_error(self):
        state = _good_state(status="zombie")
        result = _validator().validate_consistency(state)
        self.assertTrue(result["valid"])  # warnings don't fail validity
        self.assertTrue(len(result["warnings"]) > 0)

    def test_wrong_type_for_session_id_is_error(self):
        state = _good_state(session_id=12345)
        result = _validator().validate_consistency(state)
        self.assertFalse(result["valid"])


class TestFindOrphans(unittest.TestCase):
    def test_all_active_returns_empty(self):
        sessions = [_good_state(session_id="a"), _good_state(session_id="b")]
        orphans = _validator().find_orphans(sessions, {"a", "b"})
        self.assertEqual(orphans, [])

    def test_orphaned_session_detected(self):
        sessions = [_good_state(session_id="a"), _good_state(session_id="orphan")]
        orphans = _validator().find_orphans(sessions, {"a"})
        self.assertEqual(len(orphans), 1)
        self.assertEqual(orphans[0]["session_id"], "orphan")

    def test_orphan_result_has_required_fields(self):
        sessions = [_good_state(session_id="x")]
        orphans = _validator().find_orphans(sessions, set())
        self.assertIn("session_id", orphans[0])
        self.assertIn("created_at", orphans[0])
        self.assertIn("status", orphans[0])


class TestCleanupStale(unittest.TestCase):
    def test_fresh_sessions_not_stale(self):
        sessions = [_good_state(created_at=time.time() - 60)]
        result = _validator().cleanup_stale(sessions, max_age_hours=1.0)
        self.assertEqual(result["stale_count"], 0)
        self.assertEqual(result["total_count"], 1)

    def test_old_sessions_are_stale(self):
        old_time = time.time() - 25 * 3600  # 25 hours ago
        sessions = [_good_state(created_at=old_time)]
        result = _validator().cleanup_stale(sessions, max_age_hours=24.0)
        self.assertEqual(result["stale_count"], 1)
        self.assertEqual(len(result["stale_sessions"]), 1)

    def test_mixed_sessions(self):
        sessions = [
            _good_state(session_id="fresh", created_at=time.time() - 60),
            _good_state(session_id="stale", created_at=time.time() - 100000),
        ]
        result = _validator().cleanup_stale(sessions, max_age_hours=1.0)
        self.assertEqual(result["stale_count"], 1)
        self.assertEqual(result["total_count"], 2)


class TestCheckIntegrity(unittest.TestCase):
    def test_valid_state_passes_integrity(self):
        # Active sessions require last_active_at
        state = _good_state(last_active_at=time.time() - 10)
        result = _validator().check_integrity(state)
        self.assertTrue(result["integrity_ok"])
        self.assertIsInstance(result["checksum"], str)
        self.assertTrue(len(result["checksum"]) > 0)

    def test_temporal_inconsistency_flagged(self):
        state = _good_state()
        state["last_active_at"] = state["created_at"] - 100  # before creation
        result = _validator().check_integrity(state)
        self.assertFalse(result["integrity_ok"])
        self.assertTrue(len(result["issues"]) > 0)

    def test_active_session_without_last_active_at_flagged(self):
        state = _good_state(status="active")
        # No last_active_at key
        result = _validator().check_integrity(state)
        self.assertFalse(result["integrity_ok"])

    def test_checksum_differs_for_different_states(self):
        r1 = _validator().check_integrity(_good_state(session_id="a"))
        r2 = _validator().check_integrity(_good_state(session_id="b"))
        self.assertNotEqual(r1["checksum"], r2["checksum"])
