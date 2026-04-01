"""Tests for lidco.streaming.progress_reporter."""
from __future__ import annotations

from lidco.streaming.progress_reporter import ProgressEntry, ProgressReporter


class TestProgressEntry:
    def test_frozen(self) -> None:
        e = ProgressEntry(task="t")
        try:
            e.task = "x"  # type: ignore[misc]
            assert False, "should be frozen"
        except AttributeError:
            pass

    def test_defaults(self) -> None:
        e = ProgressEntry(task="t")
        assert e.current == 0
        assert e.total == 0
        assert e.parent_task == ""


class TestProgressReporter:
    def test_start(self) -> None:
        r = ProgressReporter()
        e = r.start("build", total=100)
        assert e.task == "build"
        assert e.total == 100

    def test_update(self) -> None:
        r = ProgressReporter()
        r.start("build", total=50)
        e = r.update("build", 25)
        assert e is not None
        assert e.current == 25

    def test_update_unknown(self) -> None:
        r = ProgressReporter()
        assert r.update("nope", 1) is None

    def test_complete(self) -> None:
        r = ProgressReporter()
        r.start("build", total=10)
        e = r.complete("build", "finished")
        assert e is not None
        assert e.current == 10
        assert e.phase == "complete"

    def test_complete_unknown(self) -> None:
        r = ProgressReporter()
        assert r.complete("nope") is None

    def test_percentage(self) -> None:
        r = ProgressReporter()
        r.start("t", total=200)
        r.update("t", 100)
        assert r.percentage("t") == 50.0

    def test_percentage_unknown(self) -> None:
        r = ProgressReporter()
        assert r.percentage("nope") == 0.0

    def test_eta_none_when_no_progress(self) -> None:
        r = ProgressReporter()
        r.start("t", total=100)
        assert r.eta("t") is None

    def test_subtask(self) -> None:
        r = ProgressReporter()
        r.start("parent", total=10)
        sub = r.start_subtask("parent", "child", total=5)
        assert sub.parent_task == "parent"
        assert sub.total == 5

    def test_get_active(self) -> None:
        r = ProgressReporter()
        r.start("a", total=10)
        r.start("b", total=5)
        r.complete("b")
        active = r.get_active()
        names = [e.task for e in active]
        assert "a" in names
        assert "b" not in names

    def test_summary_empty(self) -> None:
        r = ProgressReporter()
        assert "No progress" in r.summary()

    def test_summary_with_entries(self) -> None:
        r = ProgressReporter()
        r.start("build", total=100, phase="compile")
        r.update("build", 50)
        s = r.summary()
        assert "build" in s
        assert "50.0%" in s
