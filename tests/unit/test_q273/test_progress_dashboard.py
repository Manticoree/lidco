"""Tests for Q273 ProgressDashboard widget."""
from __future__ import annotations

import unittest

from lidco.widgets.progress_dashboard import ProgressDashboard, TaskProgress


class TestTaskProgress(unittest.TestCase):
    def test_defaults(self):
        t = TaskProgress(id="t1", name="test")
        assert t.progress == 0.0
        assert t.status == "pending"
        assert t.parent_id is None


class TestProgressDashboard(unittest.TestCase):
    def test_add_task(self):
        d = ProgressDashboard()
        t = d.add_task("build")
        assert t.name == "build"
        assert t.status == "pending"
        assert t.started_at is not None

    def test_update_task(self):
        d = ProgressDashboard()
        t = d.add_task("build")
        updated = d.update_task(t.id, 50.0)
        assert updated is not None
        assert updated.progress == 50.0
        assert updated.status == "running"

    def test_update_nonexistent(self):
        d = ProgressDashboard()
        assert d.update_task("nope", 10.0) is None

    def test_complete_task(self):
        d = ProgressDashboard()
        t = d.add_task("test")
        done = d.complete_task(t.id)
        assert done is not None
        assert done.progress == 100.0
        assert done.status == "complete"

    def test_complete_nonexistent(self):
        d = ProgressDashboard()
        assert d.complete_task("nope") is None

    def test_remove_task(self):
        d = ProgressDashboard()
        t = d.add_task("x")
        assert d.remove_task(t.id) is True
        assert d.remove_task(t.id) is False

    def test_nested_tasks(self):
        d = ProgressDashboard()
        parent = d.add_task("parent")
        child = d.add_task("child", parent_id=parent.id)
        kids = d.children(parent.id)
        assert len(kids) == 1
        assert kids[0].id == child.id

    def test_overall_progress(self):
        d = ProgressDashboard()
        t1 = d.add_task("a")
        t2 = d.add_task("b")
        d.update_task(t1.id, 100.0)
        d.update_task(t2.id, 50.0)
        assert d.overall_progress() == 75.0

    def test_overall_progress_empty(self):
        d = ProgressDashboard()
        assert d.overall_progress() == 0.0

    def test_overall_excludes_children(self):
        d = ProgressDashboard()
        parent = d.add_task("p")
        d.add_task("c", parent_id=parent.id)
        d.update_task(parent.id, 60.0)
        # Only parent counts for overall
        assert d.overall_progress() == 60.0

    def test_all_tasks(self):
        d = ProgressDashboard()
        d.add_task("a")
        d.add_task("b")
        assert len(d.all_tasks()) == 2

    def test_get_task(self):
        d = ProgressDashboard()
        t = d.add_task("x")
        assert d.get_task(t.id) is t
        assert d.get_task("nope") is None

    def test_render(self):
        d = ProgressDashboard()
        d.add_task("build")
        r = d.render()
        assert "ProgressDashboard" in r
        assert "build" in r

    def test_summary(self):
        d = ProgressDashboard()
        t = d.add_task("a")
        d.complete_task(t.id)
        s = d.summary()
        assert s["total"] == 1
        assert s["complete"] == 1


if __name__ == "__main__":
    unittest.main()
