"""Tests for lidco.productivity.standup — Daily Standup."""

from __future__ import annotations

import datetime
import unittest
from unittest import mock

from lidco.productivity.standup import CommitInfo, StandupGenerator, StandupNote


class TestCommitInfo(unittest.TestCase):
    def test_create(self) -> None:
        c = CommitInfo(
            hash="abc123",
            date=datetime.datetime.now(tz=datetime.timezone.utc),
            subject="Fix bug",
            author="dev",
        )
        self.assertEqual(c.hash, "abc123")
        self.assertEqual(c.subject, "Fix bug")


class TestStandupNote(unittest.TestCase):
    def test_format_basic(self) -> None:
        note = StandupNote(
            date=datetime.date(2026, 4, 5),
            yesterday=["Fixed auth bug"],
            today=["Write tests"],
            blockers=["Waiting on API access"],
        )
        text = note.format()
        self.assertIn("2026-04-05", text)
        self.assertIn("Fixed auth bug", text)
        self.assertIn("Write tests", text)
        self.assertIn("Waiting on API access", text)

    def test_format_empty_sections(self) -> None:
        note = StandupNote(
            date=datetime.date(2026, 4, 5),
            yesterday=[],
            today=[],
            blockers=[],
        )
        text = note.format()
        self.assertIn("(no items)", text)
        self.assertIn("(none)", text)

    def test_format_with_commits(self) -> None:
        commits = [
            CommitInfo(
                hash="abc1234",
                date=datetime.datetime.now(tz=datetime.timezone.utc),
                subject="Fix bug",
                author="dev",
            )
        ]
        note = StandupNote(
            date=datetime.date(2026, 4, 5),
            yesterday=["Fix bug"],
            today=["Tests"],
            blockers=[],
            commits=commits,
        )
        text = note.format()
        self.assertIn("Commits (1)", text)
        self.assertIn("[abc1234]", text)


class TestStandupGenerator(unittest.TestCase):
    def test_set_plans(self) -> None:
        gen = StandupGenerator()
        gen.set_plans(["A", "B"])
        gen.add_plan("C")
        # Plans are used in generate

    def test_set_blockers(self) -> None:
        gen = StandupGenerator()
        gen.set_blockers(["X"])
        gen.add_blocker("Y")

    def test_clear(self) -> None:
        gen = StandupGenerator()
        gen.add_plan("A")
        gen.add_blocker("B")
        gen.clear()
        # After clear, generate returns defaults

    @mock.patch("lidco.productivity.standup.subprocess.run")
    def test_get_yesterday_commits(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout="abc123|2026-04-04T10:00:00+00:00|Dev|Fix login\ndef456|2026-04-04T09:00:00+00:00|Dev|Add tests\n",
        )
        gen = StandupGenerator()
        commits = gen.get_yesterday_commits()
        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0].subject, "Fix login")
        self.assertEqual(commits[0].author, "Dev")

    @mock.patch("lidco.productivity.standup.subprocess.run")
    def test_get_yesterday_commits_failure(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(returncode=1, stdout="")
        gen = StandupGenerator()
        commits = gen.get_yesterday_commits()
        self.assertEqual(commits, [])

    @mock.patch("lidco.productivity.standup.subprocess.run")
    def test_get_yesterday_commits_exception(self, mock_run: mock.MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError
        gen = StandupGenerator()
        commits = gen.get_yesterday_commits()
        self.assertEqual(commits, [])

    @mock.patch("lidco.productivity.standup.subprocess.run")
    def test_generate(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout="abc|2026-04-04T10:00:00+00:00|Dev|Fix bug\n",
        )
        gen = StandupGenerator()
        gen.set_plans(["Write more tests"])
        gen.set_blockers(["CI is slow"])
        note = gen.generate(date=datetime.date(2026, 4, 5))
        self.assertEqual(note.date, datetime.date(2026, 4, 5))
        self.assertIn("Fix bug", note.yesterday)
        self.assertIn("Write more tests", note.today)
        self.assertIn("CI is slow", note.blockers)

    @mock.patch("lidco.productivity.standup.subprocess.run")
    def test_generate_no_commits(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(returncode=0, stdout="")
        gen = StandupGenerator()
        note = gen.generate()
        self.assertIn("No commits found", note.yesterday)

    @mock.patch("lidco.productivity.standup.subprocess.run")
    def test_format_slack(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(returncode=0, stdout="")
        gen = StandupGenerator()
        gen.set_blockers(["Blocked on deploy"])
        note = gen.generate()
        slack = gen.format_slack(note)
        self.assertIn("*Standup", slack)
        self.assertIn("*Yesterday:*", slack)
        self.assertIn("*Today:*", slack)
        self.assertIn("*Blockers:*", slack)
        self.assertIn("Blocked on deploy", slack)

    @mock.patch("lidco.productivity.standup.subprocess.run")
    def test_get_commits_since(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout="abc|2026-04-01T10:00:00+00:00|Dev|Commit\n",
        )
        gen = StandupGenerator()
        commits = gen.get_commits_since(since="2026-04-01", until="2026-04-02", author="Dev")
        self.assertEqual(len(commits), 1)
        # Verify author flag was passed
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any("--author=Dev" in a for a in call_args))


if __name__ == "__main__":
    unittest.main()
