"""Tests for lidco.session.loader — SessionLoader."""
from __future__ import annotations

import unittest

from lidco.session.persister import SessionPersister
from lidco.session.loader import SessionLoader


class TestSessionLoader(unittest.TestCase):
    def setUp(self):
        self.p = SessionPersister(":memory:")
        self.p.save("s1", [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ], config={"model": "gpt-4"})
        # Loader needs same connection, so use persister's db
        self.loader = SessionLoader.__new__(SessionLoader)
        self.loader._db_path = ":memory:"
        self.loader._conn = self.p._conn  # share connection

    def tearDown(self):
        self.p.close()

    def test_load(self):
        session = self.loader.load("s1")
        self.assertIsNotNone(session)
        self.assertEqual(session["id"], "s1")
        self.assertEqual(len(session["messages"]), 2)
        self.assertEqual(session["config"]["model"], "gpt-4")

    def test_load_nonexistent(self):
        self.assertIsNone(self.loader.load("nope"))

    def test_load_partial(self):
        session = self.loader.load_partial("s1", last_n=1)
        self.assertIsNotNone(session)
        self.assertEqual(len(session["messages"]), 1)
        self.assertEqual(session["messages"][0]["role"], "assistant")

    def test_load_partial_nonexistent(self):
        self.assertIsNone(self.loader.load_partial("nope"))

    def test_validate_integrity_valid(self):
        valid, errors = self.loader.validate_integrity("s1")
        self.assertTrue(valid)
        self.assertEqual(errors, [])

    def test_validate_integrity_not_found(self):
        valid, errors = self.loader.validate_integrity("nope")
        self.assertFalse(valid)
        self.assertIn("not found", errors[0])

    def test_migrate_schema_exists(self):
        self.assertTrue(self.loader.migrate_schema("s1"))

    def test_migrate_schema_not_found(self):
        self.assertFalse(self.loader.migrate_schema("nope"))

    def test_migrate_schema_invalid_version(self):
        self.assertFalse(self.loader.migrate_schema("s1", target_version=0))


if __name__ == "__main__":
    unittest.main()
