"""Tests for lidco.productivity.timer — Time Tracker."""

from __future__ import annotations

import asyncio
import datetime
import json
import unittest
from unittest import mock

from lidco.productivity.timer import (
    ProjectAllocation,
    TimeEntry,
    TimeReport,
    TimeTracker,
    _detect_project,
    _format_duration,
)


class TestTimeEntry(unittest.TestCase):
    """Tests for TimeEntry dataclass."""

    def test_create_entry(self) -> None:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        entry = TimeEntry(task="fix bug", project="lidco", start=now)
        self.assertEqual(entry.task, "fix bug")
        self.assertEqual(entry.project, "lidco")
        self.assertIsNone(entry.end)
        self.assertEqual(entry.tags, ())

    def test_duration_no_end(self) -> None:
        start = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(minutes=10)
        entry = TimeEntry(task="t", project="p", start=start)
        dur = entry.duration()
        self.assertGreater(dur.total_seconds(), 500)

    def test_duration_with_end(self) -> None:
        start = datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2026, 1, 1, 11, 30, tzinfo=datetime.timezone.utc)
        entry = TimeEntry(task="t", project="p", start=start, end=end)
        self.assertAlmostEqual(entry.duration().total_seconds(), 5400.0)

    def test_with_end(self) -> None:
        start = datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
        entry = TimeEntry(task="t", project="p", start=start, tags=("a",))
        end = datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.timezone.utc)
        updated = entry.with_end(end)
        self.assertEqual(updated.end, end)
        self.assertEqual(updated.task, "t")
        self.assertEqual(updated.tags, ("a",))
        self.assertIsNone(entry.end)  # original unchanged

    def test_to_dict_and_from_dict(self) -> None:
        start = datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.timezone.utc)
        entry = TimeEntry(task="t", project="p", start=start, end=end, tags=("git",))
        d = entry.to_dict()
        restored = TimeEntry.from_dict(d)
        self.assertEqual(restored.task, "t")
        self.assertEqual(restored.project, "p")
        self.assertEqual(restored.end, end)
        self.assertEqual(restored.tags, ("git",))

    def test_from_dict_no_end(self) -> None:
        data = {
            "task": "x",
            "project": "y",
            "start": "2026-01-01T10:00:00+00:00",
            "end": None,
            "tags": [],
        }
        entry = TimeEntry.from_dict(data)
        self.assertIsNone(entry.end)

    def test_frozen(self) -> None:
        entry = TimeEntry(
            task="t",
            project="p",
            start=datetime.datetime.now(tz=datetime.timezone.utc),
        )
        with self.assertRaises(AttributeError):
            entry.task = "other"  # type: ignore[misc]


class TestTimeTracker(unittest.TestCase):
    """Tests for TimeTracker."""

    def test_start_stop(self) -> None:
        tracker = TimeTracker()
        entry = tracker.start("task1", project="proj")
        self.assertEqual(entry.task, "task1")
        self.assertIsNotNone(tracker.active)

        completed = tracker.stop()
        self.assertIsNotNone(completed)
        self.assertIsNotNone(completed.end)
        self.assertIsNone(tracker.active)
        self.assertEqual(len(tracker.entries), 1)

    def test_stop_no_active(self) -> None:
        tracker = TimeTracker()
        self.assertIsNone(tracker.stop())

    def test_start_auto_stops_previous(self) -> None:
        tracker = TimeTracker()
        tracker.start("task1")
        tracker.start("task2")
        self.assertEqual(len(tracker.entries), 1)
        self.assertEqual(tracker.entries[0].task, "task1")
        self.assertEqual(tracker.active.task, "task2")

    def test_start_with_tags(self) -> None:
        tracker = TimeTracker()
        entry = tracker.start("t", tags=["a", "b"])
        self.assertEqual(entry.tags, ("a", "b"))

    def test_report_empty(self) -> None:
        tracker = TimeTracker()
        report = tracker.report()
        self.assertEqual(report.total_seconds, 0.0)
        self.assertEqual(len(report.allocations), 0)

    def test_report_with_entries(self) -> None:
        tracker = TimeTracker()
        tracker.start("t1", project="A")
        tracker.stop()
        tracker.start("t2", project="B")
        tracker.stop()
        report = tracker.report()
        self.assertEqual(len(report.allocations), 2)
        self.assertIsInstance(report.summary(), str)

    def test_export_import_json(self) -> None:
        tracker = TimeTracker()
        tracker.start("t1", project="p1")
        tracker.stop()

        exported = tracker.export_json()
        data = json.loads(exported)
        self.assertEqual(len(data), 1)

        tracker2 = TimeTracker()
        count = tracker2.import_json(exported)
        self.assertEqual(count, 1)
        self.assertEqual(len(tracker2.entries), 1)

    @mock.patch("lidco.productivity.timer.subprocess.run")
    def test_detect_from_git(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout="abc123|2026-01-01T10:00:00+00:00|Fix bug\ndef456|2026-01-01T09:00:00+00:00|Add feature\n",
        )
        tracker = TimeTracker()
        entries = tracker.detect_from_git("/repo", limit=10)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].task, "Fix bug")
        self.assertIn("git", entries[0].tags)

    @mock.patch("lidco.productivity.timer.subprocess.run")
    def test_detect_from_git_failure(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(returncode=1, stdout="")
        tracker = TimeTracker()
        entries = tracker.detect_from_git()
        self.assertEqual(entries, [])

    @mock.patch("lidco.productivity.timer.subprocess.run")
    def test_detect_from_git_exception(self, mock_run: mock.MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("git not found")
        tracker = TimeTracker()
        entries = tracker.detect_from_git()
        self.assertEqual(entries, [])


class TestFormatDuration(unittest.TestCase):
    def test_minutes_only(self) -> None:
        self.assertEqual(_format_duration(300), "5m")

    def test_hours_and_minutes(self) -> None:
        self.assertEqual(_format_duration(3660), "1h 1m")

    def test_zero(self) -> None:
        self.assertEqual(_format_duration(0), "0m")


class TestDetectProject(unittest.TestCase):
    @mock.patch("lidco.productivity.timer.subprocess.run")
    def test_from_remote(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout="https://github.com/user/myproject.git\n",
        )
        self.assertEqual(_detect_project("."), "myproject")

    @mock.patch("lidco.productivity.timer.subprocess.run")
    def test_fallback_to_dirname(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(returncode=1, stdout="")
        name = _detect_project(".")
        self.assertIsInstance(name, str)
        self.assertTrue(len(name) > 0)


class TestTimeReportSummary(unittest.TestCase):
    def test_summary_format(self) -> None:
        report = TimeReport(
            period_start=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            period_end=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
            allocations=[
                ProjectAllocation(project="A", total_seconds=3600, entry_count=2, tasks=["t1"]),
            ],
            total_seconds=3600,
        )
        summary = report.summary()
        self.assertIn("Time Report", summary)
        self.assertIn("A:", summary)
        self.assertIn("100%", summary)

    def test_summary_zero_total(self) -> None:
        report = TimeReport(
            period_start=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            period_end=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
            allocations=[
                ProjectAllocation(project="A", total_seconds=0, entry_count=0, tasks=[]),
            ],
            total_seconds=0,
        )
        summary = report.summary()
        self.assertIn("0%", summary)


if __name__ == "__main__":
    unittest.main()
