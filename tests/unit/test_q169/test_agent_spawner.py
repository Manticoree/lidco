"""Tests for AgentSpawner."""
from __future__ import annotations

import unittest

from lidco.cloud.agent_spawner import AgentHandle, AgentSpawner


class TestAgentHandle(unittest.TestCase):
    def test_dataclass_fields(self):
        h = AgentHandle(
            agent_id="abc",
            prompt="fix bug",
            model="gpt-4",
            status="queued",
            created_at=1.0,
        )
        self.assertEqual(h.agent_id, "abc")
        self.assertEqual(h.prompt, "fix bug")
        self.assertEqual(h.model, "gpt-4")
        self.assertEqual(h.status, "queued")
        self.assertAlmostEqual(h.created_at, 1.0)
        self.assertIsNone(h.worktree_path)
        self.assertIsNone(h.branch_name)

    def test_optional_fields(self):
        h = AgentHandle(
            agent_id="x",
            prompt="p",
            model="m",
            status="running",
            created_at=0,
            worktree_path="/tmp/wt",
            branch_name="agent/fix",
        )
        self.assertEqual(h.worktree_path, "/tmp/wt")
        self.assertEqual(h.branch_name, "agent/fix")


class TestAgentSpawnerSpawn(unittest.TestCase):
    def setUp(self):
        self.spawner = AgentSpawner()

    def test_spawn_returns_handle(self):
        h = self.spawner.spawn("do stuff")
        self.assertIsInstance(h, AgentHandle)
        self.assertEqual(h.status, "queued")

    def test_spawn_generates_unique_ids(self):
        h1 = self.spawner.spawn("task 1")
        h2 = self.spawner.spawn("task 2")
        self.assertNotEqual(h1.agent_id, h2.agent_id)

    def test_spawn_sets_branch_name(self):
        h = self.spawner.spawn("Fix the login bug")
        self.assertTrue(h.branch_name.startswith("agent/"))

    def test_spawn_sets_worktree_path(self):
        h = self.spawner.spawn("something")
        self.assertIn(h.agent_id, h.worktree_path)

    def test_spawn_custom_model(self):
        h = self.spawner.spawn("task", model="claude-4")
        self.assertEqual(h.model, "claude-4")

    def test_spawn_empty_model_default(self):
        h = self.spawner.spawn("task")
        self.assertEqual(h.model, "")


class TestAgentSpawnerStart(unittest.TestCase):
    def setUp(self):
        self.spawner = AgentSpawner()

    def test_start_marks_running(self):
        h = self.spawner.spawn("task")
        started = self.spawner.start(h.agent_id)
        self.assertEqual(started.status, "running")

    def test_start_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.spawner.start("nonexistent")

    def test_start_with_execute_fn(self):
        h = self.spawner.spawn("task")
        called = []
        result = self.spawner.start(h.agent_id, execute_fn=lambda handle: called.append(handle))
        self.assertEqual(len(called), 1)
        self.assertEqual(result.status, "completed")

    def test_start_execute_fn_failure(self):
        h = self.spawner.spawn("task")

        def fail(handle):
            raise RuntimeError("boom")

        result = self.spawner.start(h.agent_id, execute_fn=fail)
        self.assertEqual(result.status, "failed")


class TestAgentSpawnerGet(unittest.TestCase):
    def setUp(self):
        self.spawner = AgentSpawner()

    def test_get_existing(self):
        h = self.spawner.spawn("task")
        got = self.spawner.get(h.agent_id)
        self.assertIsNotNone(got)
        self.assertEqual(got.agent_id, h.agent_id)

    def test_get_nonexistent(self):
        self.assertIsNone(self.spawner.get("nope"))


class TestAgentSpawnerCancel(unittest.TestCase):
    def setUp(self):
        self.spawner = AgentSpawner()

    def test_cancel_queued(self):
        h = self.spawner.spawn("task")
        self.assertTrue(self.spawner.cancel(h.agent_id))
        self.assertEqual(self.spawner.get(h.agent_id).status, "failed")

    def test_cancel_nonexistent(self):
        self.assertFalse(self.spawner.cancel("nope"))

    def test_cancel_completed_returns_false(self):
        h = self.spawner.spawn("task")
        self.spawner.start(h.agent_id, execute_fn=lambda _: None)
        self.assertFalse(self.spawner.cancel(h.agent_id))


class TestAgentSpawnerListAll(unittest.TestCase):
    def test_empty(self):
        spawner = AgentSpawner()
        self.assertEqual(spawner.list_all(), [])

    def test_multiple(self):
        spawner = AgentSpawner()
        spawner.spawn("a")
        spawner.spawn("b")
        self.assertEqual(len(spawner.list_all()), 2)


class TestGenerateBranchName(unittest.TestCase):
    def test_simple(self):
        spawner = AgentSpawner()
        name = spawner._generate_branch_name("Fix login bug")
        self.assertTrue(name.startswith("agent/"))
        self.assertIn("fix", name)

    def test_long_prompt_truncated(self):
        spawner = AgentSpawner()
        name = spawner._generate_branch_name("a" * 100)
        self.assertTrue(len(name) <= 50 + len("agent/"))

    def test_empty_prompt(self):
        spawner = AgentSpawner()
        name = spawner._generate_branch_name("")
        self.assertEqual(name, "agent/agent-task")

    def test_special_chars(self):
        spawner = AgentSpawner()
        name = spawner._generate_branch_name("Fix @#$ issue!")
        self.assertNotIn("@", name)
        self.assertNotIn("#", name)


if __name__ == "__main__":
    unittest.main()
