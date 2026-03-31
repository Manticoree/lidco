"""Tests for AgentPoolManager."""
from __future__ import annotations

import unittest

from lidco.cloud.agent_spawner import AgentSpawner
from lidco.cloud.status_tracker import StatusTracker
from lidco.cloud.pool_manager import AgentPoolManager, PoolStats


class TestPoolStats(unittest.TestCase):
    def test_fields(self):
        s = PoolStats(total=5, running=2, queued=1, completed=1, failed=1)
        self.assertEqual(s.total, 5)
        self.assertEqual(s.running, 2)


class TestAgentPoolManagerSubmit(unittest.TestCase):
    def setUp(self):
        self.pool = AgentPoolManager(AgentSpawner(), StatusTracker())

    def test_submit_returns_id(self):
        aid = self.pool.submit("do stuff")
        self.assertIsInstance(aid, str)
        self.assertTrue(len(aid) > 0)

    def test_submit_creates_handle(self):
        aid = self.pool.submit("task")
        handle = self.pool.spawner.get(aid)
        self.assertIsNotNone(handle)
        self.assertEqual(handle.prompt, "task")

    def test_submit_starts_tracking(self):
        aid = self.pool.submit("task")
        log = self.pool.tracker.get_log(aid)
        self.assertIsNotNone(log)


class TestAgentPoolManagerCancel(unittest.TestCase):
    def setUp(self):
        self.pool = AgentPoolManager(AgentSpawner(), StatusTracker())

    def test_cancel_queued(self):
        aid = self.pool.submit("task")
        ok = self.pool.cancel(aid)
        self.assertTrue(ok)

    def test_cancel_nonexistent(self):
        self.assertFalse(self.pool.cancel("nope"))

    def test_cancel_marks_tracker_failed(self):
        aid = self.pool.submit("task")
        self.pool.cancel(aid)
        log = self.pool.tracker.get_log(aid)
        self.assertEqual(log.error, "Cancelled by user")


class TestAgentPoolManagerStats(unittest.TestCase):
    def test_empty(self):
        pool = AgentPoolManager(AgentSpawner(), StatusTracker())
        s = pool.stats()
        self.assertEqual(s.total, 0)

    def test_after_submit(self):
        pool = AgentPoolManager(AgentSpawner(), StatusTracker())
        pool.submit("a")
        pool.submit("b")
        s = pool.stats()
        self.assertEqual(s.total, 2)
        self.assertEqual(s.queued, 2)


class TestAgentPoolManagerResults(unittest.TestCase):
    def test_results_after_submit(self):
        pool = AgentPoolManager(AgentSpawner(), StatusTracker())
        aid = pool.submit("task")
        log = pool.results(aid)
        self.assertIsNotNone(log)

    def test_results_nonexistent(self):
        pool = AgentPoolManager(AgentSpawner(), StatusTracker())
        self.assertIsNone(pool.results("nope"))


class TestAgentPoolManagerDrain(unittest.TestCase):
    def test_drain_returns_ids(self):
        pool = AgentPoolManager(AgentSpawner(), StatusTracker())
        aid = pool.submit("task")
        ids = pool.drain()
        self.assertIn(aid, ids)

    def test_drain_empty(self):
        pool = AgentPoolManager(AgentSpawner(), StatusTracker())
        self.assertEqual(pool.drain(), [])


class TestAgentPoolManagerClearCompleted(unittest.TestCase):
    def test_clear_completed(self):
        pool = AgentPoolManager(AgentSpawner(), StatusTracker())
        aid = pool.submit("task")
        pool.spawner.start(aid, execute_fn=lambda _: None)
        pool.clear_completed()
        self.assertIsNone(pool.spawner.get(aid))

    def test_clear_keeps_queued(self):
        pool = AgentPoolManager(AgentSpawner(), StatusTracker())
        aid = pool.submit("task")
        pool.clear_completed()
        self.assertIsNotNone(pool.spawner.get(aid))


if __name__ == "__main__":
    unittest.main()
