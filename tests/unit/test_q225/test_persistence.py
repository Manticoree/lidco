"""Tests for JobPersistenceStore (Q225)."""
import time
import unittest

from lidco.jobs.persistence import JobPersistenceStore, JobRecord


class TestJobPersistenceStore(unittest.TestCase):
    def setUp(self):
        self.store = JobPersistenceStore(":memory:")

    def tearDown(self):
        self.store.close()

    def _make_record(self, **overrides):
        defaults = dict(
            id="j1",
            name="test-job",
            status="pending",
            payload='{"key": "val"}',
            result=None,
            created_at=time.time(),
            updated_at=time.time(),
            error=None,
        )
        defaults.update(overrides)
        return JobRecord(**defaults)

    # -- save / get ------------------------------------------------

    def test_save_and_get(self):
        rec = self._make_record()
        saved = self.store.save(rec)
        self.assertEqual(saved.id, "j1")
        fetched = self.store.get("j1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "test-job")

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.store.get("nope"))

    def test_save_upsert(self):
        rec = self._make_record(status="pending")
        self.store.save(rec)
        rec2 = self._make_record(status="running")
        self.store.save(rec2)
        fetched = self.store.get("j1")
        self.assertEqual(fetched.status, "running")

    def test_save_updates_updated_at(self):
        rec = self._make_record(updated_at=1000.0)
        saved = self.store.save(rec)
        self.assertGreater(saved.updated_at, 1000.0)

    # -- query -----------------------------------------------------

    def test_query_all(self):
        self.store.save(self._make_record(id="a", name="alpha"))
        self.store.save(self._make_record(id="b", name="beta"))
        results = self.store.query()
        self.assertEqual(len(results), 2)

    def test_query_by_status(self):
        self.store.save(self._make_record(id="a", status="pending"))
        self.store.save(self._make_record(id="b", status="running"))
        results = self.store.query(status="running")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "b")

    def test_query_by_name(self):
        self.store.save(self._make_record(id="a", name="alpha"))
        self.store.save(self._make_record(id="b", name="beta"))
        results = self.store.query(name="alpha")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "a")

    def test_query_limit(self):
        for i in range(10):
            self.store.save(self._make_record(id=f"j{i}"))
        results = self.store.query(limit=3)
        self.assertEqual(len(results), 3)

    # -- update_status ---------------------------------------------

    def test_update_status(self):
        self.store.save(self._make_record())
        updated = self.store.update_status("j1", "completed", result='{"ok": true}')
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "completed")
        self.assertEqual(updated.result, '{"ok": true}')

    def test_update_status_with_error(self):
        self.store.save(self._make_record())
        updated = self.store.update_status("j1", "failed", error="boom")
        self.assertEqual(updated.status, "failed")
        self.assertEqual(updated.error, "boom")

    def test_update_status_nonexistent(self):
        self.assertIsNone(self.store.update_status("nope", "failed"))

    # -- delete ----------------------------------------------------

    def test_delete(self):
        self.store.save(self._make_record())
        self.assertTrue(self.store.delete("j1"))
        self.assertIsNone(self.store.get("j1"))

    def test_delete_nonexistent(self):
        self.assertFalse(self.store.delete("nope"))

    # -- cleanup ---------------------------------------------------

    def test_cleanup_removes_old_completed(self):
        old_time = time.time() - 7200
        self.store.save(self._make_record(id="old", status="completed"))
        # Manually backdate the updated_at in the DB
        self.store._conn.execute(
            "UPDATE jobs SET updated_at = ? WHERE id = ?", (old_time, "old")
        )
        self.store._conn.commit()
        self.store.save(self._make_record(id="new", status="completed"))
        cutoff = time.time() - 3600
        removed = self.store.cleanup(cutoff)
        self.assertEqual(removed, 1)
        self.assertIsNone(self.store.get("old"))
        self.assertIsNotNone(self.store.get("new"))

    def test_cleanup_ignores_pending(self):
        old_time = time.time() - 7200
        self.store.save(self._make_record(id="p", status="pending"))
        self.store._conn.execute(
            "UPDATE jobs SET updated_at = ? WHERE id = ?", (old_time, "p")
        )
        self.store._conn.commit()
        removed = self.store.cleanup(time.time())
        self.assertEqual(removed, 0)

    # -- count -----------------------------------------------------

    def test_count_all(self):
        self.store.save(self._make_record(id="a"))
        self.store.save(self._make_record(id="b"))
        self.assertEqual(self.store.count(), 2)

    def test_count_by_status(self):
        self.store.save(self._make_record(id="a", status="pending"))
        self.store.save(self._make_record(id="b", status="running"))
        self.assertEqual(self.store.count(status="pending"), 1)

    def test_count_empty(self):
        self.assertEqual(self.store.count(), 0)


if __name__ == "__main__":
    unittest.main()
