"""Tests for Q225 CLI commands (Q225)."""
import asyncio
import time
import unittest

from lidco.jobs.persistence import JobPersistenceStore, JobRecord
from lidco.cli.commands import q225_cmds


class TestQ225Commands(unittest.TestCase):
    def setUp(self):
        self.store = JobPersistenceStore(":memory:")
        q225_cmds._state["store"] = self.store

    def tearDown(self):
        self.store.close()
        q225_cmds._state.clear()

    def _add_job(self, job_id="j1", name="test", status="pending"):
        now = time.time()
        self.store.save(JobRecord(
            id=job_id, name=name, status=status,
            payload="{}", result=None, created_at=now, updated_at=now,
        ))

    def _run(self, handler, args=""):
        return asyncio.run(handler(args))

    def test_jobs_list(self):
        # Get the handler via register
        class FakeRegistry:
            def __init__(self):
                self.cmds = {}
            def register(self, cmd):
                self.cmds[cmd.name] = cmd
        reg = FakeRegistry()
        q225_cmds.register(reg)
        handler = reg.cmds["jobs"].handler

        self._add_job("j1", "alpha")
        result = self._run(handler, "list")
        self.assertIn("alpha", result)

    def test_jobs_status(self):
        class FakeRegistry:
            def __init__(self):
                self.cmds = {}
            def register(self, cmd):
                self.cmds[cmd.name] = cmd
        reg = FakeRegistry()
        q225_cmds.register(reg)
        handler = reg.cmds["jobs"].handler

        self._add_job("j1", "alpha", "running")
        result = self._run(handler, "status j1")
        self.assertIn("running", result)
        self.assertIn("alpha", result)

    def test_jobs_status_not_found(self):
        class FakeRegistry:
            def __init__(self):
                self.cmds = {}
            def register(self, cmd):
                self.cmds[cmd.name] = cmd
        reg = FakeRegistry()
        q225_cmds.register(reg)
        result = self._run(reg.cmds["jobs"].handler, "status nope")
        self.assertIn("not found", result)

    def test_job_status_handler(self):
        class FakeRegistry:
            def __init__(self):
                self.cmds = {}
            def register(self, cmd):
                self.cmds[cmd.name] = cmd
        reg = FakeRegistry()
        q225_cmds.register(reg)
        handler = reg.cmds["job-status"].handler

        self._add_job("j1", "beta", "completed")
        result = self._run(handler, "j1")
        self.assertIn("completed", result)

    def test_job_status_empty(self):
        class FakeRegistry:
            def __init__(self):
                self.cmds = {}
            def register(self, cmd):
                self.cmds[cmd.name] = cmd
        reg = FakeRegistry()
        q225_cmds.register(reg)
        result = self._run(reg.cmds["job-status"].handler, "")
        self.assertIn("Usage", result)

    def test_job_recover_scan(self):
        class FakeRegistry:
            def __init__(self):
                self.cmds = {}
            def register(self, cmd):
                self.cmds[cmd.name] = cmd
        reg = FakeRegistry()
        q225_cmds.register(reg)
        handler = reg.cmds["job-recover"].handler

        self._add_job("r1", "stuck", "running")
        result = self._run(handler, "scan")
        self.assertIn("r1", result)

    def test_job_recover_execute(self):
        class FakeRegistry:
            def __init__(self):
                self.cmds = {}
            def register(self, cmd):
                self.cmds[cmd.name] = cmd
        reg = FakeRegistry()
        q225_cmds.register(reg)
        handler = reg.cmds["job-recover"].handler

        self._add_job("r1", "stuck", "running")
        result = self._run(handler, "execute")
        self.assertIn("resumed", result)

    def test_job_clean_handler(self):
        class FakeRegistry:
            def __init__(self):
                self.cmds = {}
            def register(self, cmd):
                self.cmds[cmd.name] = cmd
        reg = FakeRegistry()
        q225_cmds.register(reg)
        handler = reg.cmds["job-clean"].handler

        old_time = time.time() - 7200
        self.store.save(JobRecord(
            id="old", name="old-job", status="completed",
            payload="{}", result=None, created_at=old_time, updated_at=old_time,
        ))
        # Backdate updated_at since save() overwrites it
        self.store._conn.execute(
            "UPDATE jobs SET updated_at = ? WHERE id = ?", (old_time, "old")
        )
        self.store._conn.commit()
        result = self._run(handler, "1")
        self.assertIn("Cleaned 1", result)


if __name__ == "__main__":
    unittest.main()
