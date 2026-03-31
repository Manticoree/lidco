"""Tests for CrashRecovery."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.resilience.auto_checkpoint import AutoCheckpoint
from lidco.resilience.crash_recovery import CrashRecovery, RecoveryInfo


class TestCrashRecovery(unittest.TestCase):
    def setUp(self):
        self.cp_store = AutoCheckpoint(max_checkpoints=10, interval_seconds=1.0)
        self.recovery = CrashRecovery(self.cp_store)

    # --- mark_session_start / mark_session_end ---
    def test_mark_start(self):
        self.recovery.mark_session_start("s1")
        info = self.recovery.detect_crash()
        self.assertTrue(info.crash_detected)

    def test_mark_end_clean(self):
        self.recovery.mark_session_start("s1")
        self.recovery.mark_session_end("s1")
        info = self.recovery.detect_crash()
        self.assertFalse(info.crash_detected)

    def test_mark_end_unknown_session(self):
        # Should not raise
        self.recovery.mark_session_end("unknown")

    def test_multiple_sessions_clean(self):
        self.recovery.mark_session_start("s1")
        self.recovery.mark_session_end("s1")
        self.recovery.mark_session_start("s2")
        self.recovery.mark_session_end("s2")
        info = self.recovery.detect_crash()
        self.assertFalse(info.crash_detected)

    # --- detect_crash ---
    def test_detect_crash_no_sessions(self):
        info = self.recovery.detect_crash()
        self.assertFalse(info.crash_detected)

    def test_detect_crash_returns_session_id(self):
        self.recovery.mark_session_start("s1")
        info = self.recovery.detect_crash()
        self.assertEqual(info.last_session_id, "s1")

    def test_detect_crash_returns_checkpoint_data(self):
        self.cp_store.save("cp1", {"state": "saved"})
        self.recovery.mark_session_start("s1")
        info = self.recovery.detect_crash()
        self.assertEqual(info.checkpoint, {"state": "saved"})

    def test_detect_crash_no_checkpoint(self):
        self.recovery.mark_session_start("s1")
        info = self.recovery.detect_crash()
        self.assertIsNone(info.checkpoint)

    def test_detect_crash_recovery_actions(self):
        self.cp_store.save("cp1", {"state": "saved"})
        self.recovery.mark_session_start("s1")
        info = self.recovery.detect_crash()
        self.assertIn("restore_from_checkpoint", info.recovery_actions)
        self.assertIn("start_new_session", info.recovery_actions)

    def test_detect_crash_no_checkpoint_actions(self):
        self.recovery.mark_session_start("s1")
        info = self.recovery.detect_crash()
        self.assertNotIn("restore_from_checkpoint", info.recovery_actions)
        self.assertIn("start_new_session", info.recovery_actions)

    def test_detect_crash_latest_unclean(self):
        self.recovery.mark_session_start("s1")
        self.recovery.mark_session_end("s1")
        self.recovery.mark_session_start("s2")
        # s2 not ended
        info = self.recovery.detect_crash()
        self.assertTrue(info.crash_detected)
        self.assertEqual(info.last_session_id, "s2")

    # --- recover ---
    def test_recover_with_checkpoint(self):
        self.cp_store.save("cp1", {"key": "value"})
        data = self.recovery.recover()
        self.assertEqual(data, {"key": "value"})

    def test_recover_no_checkpoint(self):
        data = self.recovery.recover()
        self.assertIsNone(data)

    def test_recover_latest_checkpoint(self):
        self.cp_store.save("cp1", {"n": 1})
        self.cp_store.save("cp2", {"n": 2})
        data = self.recovery.recover()
        self.assertEqual(data, {"n": 2})

    # --- cleanup_stale ---
    def test_cleanup_stale_removes_old(self):
        self.recovery.mark_session_start("s1")
        # Manually age the session
        self.recovery._sessions["s1"]["started_at"] = time.time() - 100000
        self.recovery.cleanup_stale(max_age_seconds=1000)
        info = self.recovery.detect_crash()
        self.assertFalse(info.crash_detected)

    def test_cleanup_stale_keeps_recent(self):
        self.recovery.mark_session_start("s1")
        self.recovery.cleanup_stale(max_age_seconds=86400)
        info = self.recovery.detect_crash()
        self.assertTrue(info.crash_detected)

    def test_cleanup_stale_partial(self):
        self.recovery.mark_session_start("s1")
        self.recovery._sessions["s1"]["started_at"] = time.time() - 100000
        self.recovery.mark_session_start("s2")
        self.recovery.cleanup_stale(max_age_seconds=1000)
        info = self.recovery.detect_crash()
        self.assertTrue(info.crash_detected)
        self.assertEqual(info.last_session_id, "s2")

    # --- recovery_info dataclass ---
    def test_recovery_info_defaults(self):
        info = RecoveryInfo(crash_detected=False)
        self.assertIsNone(info.last_session_id)
        self.assertIsNone(info.checkpoint)
        self.assertEqual(info.recovery_actions, [])


if __name__ == "__main__":
    unittest.main()
