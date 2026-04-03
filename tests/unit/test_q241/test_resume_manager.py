"""Tests for lidco.session.resume_manager — ResumeManager."""
from __future__ import annotations

import unittest

from lidco.session.persister import SessionPersister
from lidco.session.loader import SessionLoader
from lidco.session.resume_manager import ResumeManager


def _make_manager():
    p = SessionPersister(":memory:")
    loader = SessionLoader.__new__(SessionLoader)
    loader._db_path = ":memory:"
    loader._conn = p._conn
    return p, loader, ResumeManager(p, loader)


class TestResumeManagerBasics(unittest.TestCase):
    def setUp(self):
        self.p, self.loader, self.rm = _make_manager()
        self.p.save("s1", [{"role": "user", "content": "hello"}])
        self.p.save("s2", [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hey"},
        ])

    def tearDown(self):
        self.p.close()

    def test_list_resumable(self):
        sessions = self.rm.list_resumable()
        self.assertEqual(len(sessions), 2)

    def test_list_resumable_limit(self):
        self.assertEqual(len(self.rm.list_resumable(limit=1)), 1)

    def test_get_last_session(self):
        session = self.rm.get_last_session()
        self.assertIsNotNone(session)
        self.assertIn("messages", session)

    def test_get_last_session_empty(self):
        p, loader, rm = _make_manager()
        self.assertIsNone(rm.get_last_session())
        p.close()

    def test_resume(self):
        session = self.rm.resume("s1")
        self.assertIsNotNone(session)
        self.assertEqual(session["id"], "s1")

    def test_resume_nonexistent(self):
        self.assertIsNone(self.rm.resume("nope"))

    def test_create_summary(self):
        summary = self.rm.create_summary("s2")
        self.assertIn("s2", summary)
        self.assertIn("Messages: 2", summary)
        self.assertIn("user: 1", summary)

    def test_create_summary_not_found(self):
        summary = self.rm.create_summary("nope")
        self.assertIn("not found", summary)

    def test_detect_conflicts_no_config(self):
        self.p.save("s3", [{"role": "user"}])
        conflicts = self.rm.detect_conflicts("s3")
        self.assertTrue(any("config" in c.lower() for c in conflicts))

    def test_detect_conflicts_empty_messages(self):
        self.p.save("s4", [])
        conflicts = self.rm.detect_conflicts("s4")
        self.assertTrue(any("no messages" in c.lower() for c in conflicts))

    def test_detect_conflicts_not_found(self):
        conflicts = self.rm.detect_conflicts("nope")
        self.assertTrue(any("not found" in c for c in conflicts))


if __name__ == "__main__":
    unittest.main()
