"""Tests for SharedTaskList (Task 713)."""
from __future__ import annotations

import threading
import unittest

from lidco.agents.shared_task_list import SharedTask, SharedTaskList, TaskStatus


class TestTaskStatus(unittest.TestCase):
    def test_pending_value(self):
        self.assertEqual(TaskStatus.PENDING.value, "pending")

    def test_claimed_value(self):
        self.assertEqual(TaskStatus.CLAIMED.value, "claimed")

    def test_done_value(self):
        self.assertEqual(TaskStatus.DONE.value, "done")

    def test_failed_value(self):
        self.assertEqual(TaskStatus.FAILED.value, "failed")


class TestSharedTask(unittest.TestCase):
    def test_defaults(self):
        t = SharedTask(id="abc", title="do thing")
        self.assertEqual(t.status, TaskStatus.PENDING)
        self.assertIsNone(t.assigned_to)
        self.assertIsNone(t.result)


class TestSharedTaskList(unittest.TestCase):
    def setUp(self):
        self.tl = SharedTaskList()

    def test_add_returns_task(self):
        task = self.tl.add("task1")
        self.assertIsInstance(task, SharedTask)
        self.assertEqual(task.title, "task1")
        self.assertEqual(task.status, TaskStatus.PENDING)

    def test_add_unique_ids(self):
        t1 = self.tl.add("a")
        t2 = self.tl.add("b")
        self.assertNotEqual(t1.id, t2.id)

    def test_add_sets_created_at(self):
        task = self.tl.add("t")
        self.assertTrue(len(task.created_at) > 0)

    def test_claim_returns_task(self):
        self.tl.add("t1")
        claimed = self.tl.claim("agent_a")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.status, TaskStatus.CLAIMED)
        self.assertEqual(claimed.assigned_to, "agent_a")

    def test_claim_empty_returns_none(self):
        result = self.tl.claim("agent")
        self.assertIsNone(result)

    def test_claim_only_pending(self):
        t = self.tl.add("t1")
        self.tl.claim("a")  # claims t1
        result = self.tl.claim("b")
        self.assertIsNone(result)

    def test_complete(self):
        t = self.tl.add("t1")
        self.tl.claim("a")
        self.tl.complete(t.id, "done!")
        all_tasks = self.tl.list_all()
        self.assertEqual(all_tasks[0].status, TaskStatus.DONE)
        self.assertEqual(all_tasks[0].result, "done!")

    def test_complete_missing_raises(self):
        with self.assertRaises(KeyError):
            self.tl.complete("nonexistent", "r")

    def test_fail(self):
        t = self.tl.add("t1")
        self.tl.claim("a")
        self.tl.fail(t.id, "oops")
        all_tasks = self.tl.list_all()
        self.assertEqual(all_tasks[0].status, TaskStatus.FAILED)
        self.assertEqual(all_tasks[0].result, "oops")

    def test_fail_missing_raises(self):
        with self.assertRaises(KeyError):
            self.tl.fail("nope", "err")

    def test_list_pending(self):
        self.tl.add("a")
        self.tl.add("b")
        self.tl.claim("x")
        pending = self.tl.list_pending()
        self.assertEqual(len(pending), 1)

    def test_list_all(self):
        self.tl.add("a")
        self.tl.add("b")
        self.assertEqual(len(self.tl.list_all()), 2)

    def test_pending_count(self):
        self.tl.add("a")
        self.tl.add("b")
        self.assertEqual(self.tl.pending_count(), 2)
        self.tl.claim("x")
        self.assertEqual(self.tl.pending_count(), 1)

    def test_done_count(self):
        t = self.tl.add("a")
        self.assertEqual(self.tl.done_count(), 0)
        self.tl.claim("x")
        self.tl.complete(t.id, "ok")
        self.assertEqual(self.tl.done_count(), 1)

    def test_reset(self):
        self.tl.add("a")
        self.tl.add("b")
        self.tl.reset()
        self.assertEqual(self.tl.list_all(), [])
        self.assertEqual(self.tl.pending_count(), 0)

    def test_concurrent_claim_no_double_assignment(self):
        """Multiple threads claiming should never assign the same task twice."""
        for _ in range(5):
            self.tl.add(f"task_{_}")

        claimed_ids: list[str] = []
        lock = threading.Lock()

        def worker(name):
            while True:
                t = self.tl.claim(name)
                if t is None:
                    break
                with lock:
                    claimed_ids.append(t.id)

        threads = [threading.Thread(target=worker, args=(f"agent_{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each task should be claimed exactly once
        self.assertEqual(len(claimed_ids), 5)
        self.assertEqual(len(set(claimed_ids)), 5)

    def test_list_pending_after_complete(self):
        t = self.tl.add("a")
        self.tl.claim("x")
        self.tl.complete(t.id, "r")
        self.assertEqual(self.tl.list_pending(), [])

    def test_list_all_preserves_order(self):
        self.tl.add("first")
        self.tl.add("second")
        tasks = self.tl.list_all()
        self.assertEqual(tasks[0].title, "first")
        self.assertEqual(tasks[1].title, "second")

    def test_done_count_excludes_failed(self):
        t = self.tl.add("a")
        self.tl.claim("x")
        self.tl.fail(t.id, "err")
        self.assertEqual(self.tl.done_count(), 0)

    def test_multiple_add_claim_complete_cycle(self):
        tasks = [self.tl.add(f"t{i}") for i in range(3)]
        for t in tasks:
            self.tl.claim("a")
        for t in tasks:
            self.tl.complete(t.id, "ok")
        self.assertEqual(self.tl.done_count(), 3)
        self.assertEqual(self.tl.pending_count(), 0)

    def test_reset_then_add(self):
        self.tl.add("old")
        self.tl.reset()
        self.tl.add("new")
        self.assertEqual(len(self.tl.list_all()), 1)
        self.assertEqual(self.tl.list_all()[0].title, "new")

    def test_claim_returns_first_pending(self):
        self.tl.add("first")
        self.tl.add("second")
        claimed = self.tl.claim("a")
        self.assertEqual(claimed.title, "first")

    def test_id_is_string(self):
        t = self.tl.add("t")
        self.assertIsInstance(t.id, str)
        self.assertTrue(len(t.id) > 0)


if __name__ == "__main__":
    unittest.main()
