"""Tests for JobRecovery (Q225)."""
import time
import unittest

from lidco.jobs.persistence import JobPersistenceStore, JobRecord
from lidco.jobs.recovery import JobRecovery, RecoveryAction


class TestJobRecovery(unittest.TestCase):
    def setUp(self):
        self.store = JobPersistenceStore(":memory:")
        self.recovery = JobRecovery(self.store, max_resume_age=3600.0)

    def tearDown(self):
        self.store.close()

    def _add_job(self, job_id, status="running", updated_at=None):
        now = time.time()
        self.store.save(JobRecord(
            id=job_id, name=f"job-{job_id}", status=status,
            payload="{}", result=None, created_at=now, updated_at=now,
        ))
        if updated_at is not None:
            self.store._conn.execute(
                "UPDATE jobs SET updated_at = ? WHERE id = ?", (updated_at, job_id)
            )
            self.store._conn.commit()

    # -- scan ------------------------------------------------------

    def test_scan_finds_running_jobs(self):
        self._add_job("r1", status="running")
        actions = self.recovery.scan()
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].job_id, "r1")

    def test_scan_ignores_non_running(self):
        self._add_job("p1", status="pending")
        self._add_job("c1", status="completed")
        actions = self.recovery.scan()
        self.assertEqual(len(actions), 0)

    def test_scan_resume_recent(self):
        self._add_job("r1", status="running", updated_at=time.time())
        actions = self.recovery.scan()
        self.assertEqual(actions[0].action, "resume")

    def test_scan_fail_old(self):
        old = time.time() - 7200  # 2 hours ago
        self._add_job("r1", status="running", updated_at=old)
        actions = self.recovery.scan()
        self.assertEqual(actions[0].action, "fail")

    def test_scan_empty(self):
        self.assertEqual(self.recovery.scan(), [])

    # -- execute ---------------------------------------------------

    def test_execute_resume(self):
        self._add_job("r1", status="running", updated_at=time.time())
        result = self.recovery.execute()
        self.assertEqual(result["resumed"], 1)
        job = self.store.get("r1")
        self.assertEqual(job.status, "pending")

    def test_execute_fail(self):
        old = time.time() - 7200
        self._add_job("r1", status="running", updated_at=old)
        result = self.recovery.execute()
        self.assertEqual(result["failed"], 1)
        job = self.store.get("r1")
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error, "interrupted")

    def test_execute_skip(self):
        actions = [RecoveryAction(job_id="x", action="skip", reason="test")]
        result = self.recovery.execute(actions)
        self.assertEqual(result["skipped"], 1)

    def test_execute_with_explicit_actions(self):
        self._add_job("r1", status="running")
        actions = [RecoveryAction(job_id="r1", action="fail", reason="forced")]
        result = self.recovery.execute(actions)
        self.assertEqual(result["failed"], 1)

    # -- mark_interrupted ------------------------------------------

    def test_mark_interrupted_running_job(self):
        self._add_job("r1", status="running")
        self.assertTrue(self.recovery.mark_interrupted("r1"))
        job = self.store.get("r1")
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error, "interrupted")

    def test_mark_interrupted_non_running(self):
        self._add_job("p1", status="pending")
        self.assertFalse(self.recovery.mark_interrupted("p1"))

    def test_mark_interrupted_nonexistent(self):
        self.assertFalse(self.recovery.mark_interrupted("nope"))


if __name__ == "__main__":
    unittest.main()
