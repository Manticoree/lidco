"""Tests for lidco.session.persister — SessionPersister."""
from __future__ import annotations

import unittest

from lidco.session.persister import SessionPersister


class TestPersisterSaveLoad(unittest.TestCase):
    def setUp(self):
        self.p = SessionPersister(":memory:")

    def tearDown(self):
        self.p.close()

    def test_save_and_exists(self):
        self.p.save("s1", [{"role": "user", "content": "hi"}])
        self.assertTrue(self.p.exists("s1"))

    def test_not_exists(self):
        self.assertFalse(self.p.exists("nope"))

    def test_save_returns_id(self):
        self.assertEqual(self.p.save("s1", []), "s1")

    def test_list_sessions(self):
        self.p.save("s1", [{"role": "user"}])
        self.p.save("s2", [{"role": "user"}, {"role": "assistant"}])
        sessions = self.p.list_sessions()
        self.assertEqual(len(sessions), 2)
        ids = {s["id"] for s in sessions}
        self.assertIn("s1", ids)
        self.assertIn("s2", ids)

    def test_list_sessions_message_count(self):
        self.p.save("s1", [{"role": "user"}, {"role": "assistant"}])
        sessions = self.p.list_sessions()
        self.assertEqual(sessions[0]["message_count"], 2)

    def test_delete(self):
        self.p.save("s1", [])
        self.assertTrue(self.p.delete("s1"))
        self.assertFalse(self.p.exists("s1"))

    def test_delete_nonexistent(self):
        self.assertFalse(self.p.delete("nope"))

    def test_save_overwrites(self):
        self.p.save("s1", [{"role": "user"}])
        self.p.save("s1", [{"role": "user"}, {"role": "assistant"}])
        sessions = self.p.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["message_count"], 2)

    def test_save_with_config(self):
        self.p.save("s1", [], config={"model": "gpt-4"})
        raw = self.p.get_raw("s1")
        self.assertIn("gpt-4", raw["config"])


class TestIncrementalSave(unittest.TestCase):
    def setUp(self):
        self.p = SessionPersister(":memory:")

    def tearDown(self):
        self.p.close()

    def test_incremental_append(self):
        self.p.save("s1", [{"role": "user", "content": "1"}])
        self.assertTrue(self.p.save_incremental("s1", [{"role": "assistant", "content": "2"}]))
        sessions = self.p.list_sessions()
        self.assertEqual(sessions[0]["message_count"], 2)

    def test_incremental_nonexistent(self):
        self.assertFalse(self.p.save_incremental("nope", []))


class TestGetRaw(unittest.TestCase):
    def test_get_raw(self):
        p = SessionPersister(":memory:")
        p.save("s1", [{"role": "user"}], metadata={"tag": "test"})
        raw = p.get_raw("s1")
        self.assertEqual(raw["id"], "s1")
        self.assertIn("tag", raw["metadata"])
        p.close()

    def test_get_raw_nonexistent(self):
        p = SessionPersister(":memory:")
        self.assertIsNone(p.get_raw("nope"))
        p.close()


if __name__ == "__main__":
    unittest.main()
