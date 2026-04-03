"""Tests for JobScheduler (Q225)."""
import unittest

from lidco.jobs.persistence import JobPersistenceStore
from lidco.jobs.scheduler import JobScheduler, ScheduledJob


class TestJobScheduler(unittest.TestCase):
    def setUp(self):
        self.store = JobPersistenceStore(":memory:")
        self.scheduler = JobScheduler(max_concurrent=2, store=self.store)

    def tearDown(self):
        self.store.close()

    # -- submit ----------------------------------------------------

    def test_submit_returns_scheduled_job(self):
        job = self.scheduler.submit("build")
        self.assertIsInstance(job, ScheduledJob)
        self.assertEqual(job.name, "build")
        self.assertEqual(job.priority, 0)

    def test_submit_with_payload_and_priority(self):
        job = self.scheduler.submit("deploy", payload='{"env":"prod"}', priority=5)
        self.assertEqual(job.payload, '{"env":"prod"}')
        self.assertEqual(job.priority, 5)

    def test_submit_persists_to_store(self):
        job = self.scheduler.submit("test")
        record = self.store.get(job.id)
        self.assertIsNotNone(record)
        self.assertEqual(record.status, "pending")

    # -- next ------------------------------------------------------

    def test_next_returns_highest_priority(self):
        self.scheduler.submit("low", priority=1)
        self.scheduler.submit("high", priority=10)
        self.scheduler.submit("mid", priority=5)
        job = self.scheduler.next()
        self.assertEqual(job.name, "high")

    def test_next_respects_concurrency(self):
        self.scheduler.submit("a")
        self.scheduler.submit("b")
        self.scheduler.submit("c")
        self.scheduler.next()
        self.scheduler.next()
        self.assertIsNone(self.scheduler.next())  # max_concurrent=2

    def test_next_empty_queue(self):
        self.assertIsNone(self.scheduler.next())

    def test_next_updates_store_to_running(self):
        job = self.scheduler.submit("x")
        self.scheduler.next()
        record = self.store.get(job.id)
        self.assertEqual(record.status, "running")

    # -- dependencies ----------------------------------------------

    def test_next_blocks_on_unmet_dependency(self):
        j1 = self.scheduler.submit("dep")
        self.scheduler.submit("main", depends_on=[j1.id])
        # Take dep first
        got = self.scheduler.next()
        self.assertEqual(got.id, j1.id)
        # main is blocked (dep not completed)
        self.assertIsNone(self.scheduler.next())

    def test_next_unblocks_after_dep_complete(self):
        j1 = self.scheduler.submit("dep")
        j2 = self.scheduler.submit("main", depends_on=[j1.id])
        self.scheduler.next()  # take j1
        self.scheduler.complete(j1.id)
        got = self.scheduler.next()
        self.assertIsNotNone(got)
        self.assertEqual(got.id, j2.id)

    def test_is_blocked(self):
        j1 = self.scheduler.submit("dep")
        j2 = self.scheduler.submit("main", depends_on=[j1.id])
        self.assertTrue(self.scheduler.is_blocked(j2.id))

    # -- complete / fail / cancel ----------------------------------

    def test_complete(self):
        job = self.scheduler.submit("x")
        self.scheduler.next()
        self.assertTrue(self.scheduler.complete(job.id, result="ok"))
        record = self.store.get(job.id)
        self.assertEqual(record.status, "completed")

    def test_complete_not_running(self):
        job = self.scheduler.submit("x")
        self.assertFalse(self.scheduler.complete(job.id))

    def test_fail(self):
        job = self.scheduler.submit("x")
        self.scheduler.next()
        self.assertTrue(self.scheduler.fail(job.id, "oops"))
        record = self.store.get(job.id)
        self.assertEqual(record.status, "failed")
        self.assertEqual(record.error, "oops")

    def test_cancel_pending(self):
        job = self.scheduler.submit("x")
        self.assertTrue(self.scheduler.cancel(job.id))
        record = self.store.get(job.id)
        self.assertEqual(record.status, "cancelled")

    def test_cancel_not_in_queue(self):
        self.assertFalse(self.scheduler.cancel("nope"))

    # -- listing ---------------------------------------------------

    def test_pending(self):
        self.scheduler.submit("a")
        self.scheduler.submit("b")
        self.assertEqual(len(self.scheduler.pending()), 2)

    def test_running(self):
        self.scheduler.submit("a")
        self.scheduler.next()
        self.assertEqual(len(self.scheduler.running()), 1)

    # -- summary ---------------------------------------------------

    def test_summary(self):
        self.scheduler.submit("a")
        j = self.scheduler.submit("b")
        self.scheduler.next()
        s = self.scheduler.summary()
        self.assertEqual(s["pending"], 1)
        self.assertEqual(s["running"], 1)
        self.assertEqual(s["max_concurrent"], 2)


if __name__ == "__main__":
    unittest.main()
