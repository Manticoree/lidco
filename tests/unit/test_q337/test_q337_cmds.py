"""Tests for lidco.cli.commands.q337_cmds — /timer, /focus, /standup, /retro."""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock


class _FakeRegistry:
    """Minimal registry for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler: object) -> None:
        self.commands[name] = (description, handler)


def _run(coro):
    return asyncio.run(coro)


class TestQ337Registration(unittest.TestCase):
    def test_registers_all_commands(self) -> None:
        from lidco.cli.commands.q337_cmds import register_q337_commands

        reg = _FakeRegistry()
        register_q337_commands(reg)
        self.assertIn("timer", reg.commands)
        self.assertIn("focus", reg.commands)
        self.assertIn("standup", reg.commands)
        self.assertIn("retro", reg.commands)


class TestTimerCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q337_cmds import register_q337_commands
        reg = _FakeRegistry()
        register_q337_commands(reg)
        return reg.commands["timer"][1]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self._handler()(""))
        self.assertIn("Usage:", result)

    def test_start(self) -> None:
        result = _run(self._handler()("start my-task --project proj --tags a,b"))
        self.assertIn("Started tracking", result)
        self.assertIn("my-task", result)
        self.assertIn("proj", result)

    def test_start_no_task(self) -> None:
        result = _run(self._handler()("start"))
        self.assertIn("Usage:", result)

    def test_stop_no_active(self) -> None:
        result = _run(self._handler()("stop"))
        self.assertIn("No active task", result)

    def test_status_no_active(self) -> None:
        result = _run(self._handler()("status"))
        self.assertIn("No active task", result)

    def test_report(self) -> None:
        result = _run(self._handler()("report"))
        self.assertIn("Time Report", result)

    @mock.patch("lidco.productivity.timer.subprocess.run")
    def test_git(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout="abc|2026-01-01T10:00:00+00:00|Fix bug\n",
        )
        result = _run(self._handler()("git --limit 5"))
        self.assertIn("Detected", result)

    @mock.patch("lidco.productivity.timer.subprocess.run")
    def test_git_no_commits(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(returncode=0, stdout="")
        result = _run(self._handler()("git"))
        self.assertIn("No git commits", result)

    def test_export(self) -> None:
        result = _run(self._handler()("export"))
        self.assertIn("[", result)  # JSON array

    def test_unknown_subcmd(self) -> None:
        result = _run(self._handler()("unknown"))
        self.assertIn("Unknown subcommand", result)


class TestFocusCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q337_cmds import register_q337_commands
        reg = _FakeRegistry()
        register_q337_commands(reg)
        return reg.commands["focus"][1]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self._handler()(""))
        self.assertIn("Usage:", result)

    def test_start(self) -> None:
        result = _run(self._handler()("start --work 30 --break 10"))
        self.assertIn("Focus mode started", result)
        self.assertIn("30m", result)
        self.assertIn("10m", result)

    def test_stop_no_session(self) -> None:
        result = _run(self._handler()("stop"))
        self.assertIn("No active focus session", result)

    def test_pause_no_session(self) -> None:
        result = _run(self._handler()("pause"))
        self.assertIn("No active session", result)

    def test_resume_no_session(self) -> None:
        result = _run(self._handler()("resume"))
        self.assertIn("No paused session", result)

    def test_status(self) -> None:
        result = _run(self._handler()("status"))
        self.assertIn("Focus state:", result)

    def test_stats(self) -> None:
        result = _run(self._handler()("stats"))
        self.assertIn("Focus stats:", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self._handler()("unknown"))
        self.assertIn("Unknown subcommand", result)


class TestStandupCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q337_cmds import register_q337_commands
        reg = _FakeRegistry()
        register_q337_commands(reg)
        return reg.commands["standup"][1]

    @mock.patch("lidco.productivity.standup.subprocess.run")
    def test_no_args_generates(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(returncode=0, stdout="")
        result = _run(self._handler()(""))
        self.assertIn("Standup", result)

    def test_plan(self) -> None:
        result = _run(self._handler()("plan Write more tests"))
        self.assertIn("Added plan", result)

    def test_plan_no_item(self) -> None:
        result = _run(self._handler()("plan"))
        self.assertIn("Usage:", result)

    def test_blocker(self) -> None:
        result = _run(self._handler()("blocker CI is broken"))
        self.assertIn("Added blocker", result)

    def test_blocker_no_item(self) -> None:
        result = _run(self._handler()("blocker"))
        self.assertIn("Usage:", result)

    @mock.patch("lidco.productivity.standup.subprocess.run")
    def test_slack(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.Mock(returncode=0, stdout="")
        result = _run(self._handler()("slack"))
        self.assertIn("*Standup", result)

    def test_clear(self) -> None:
        result = _run(self._handler()("clear"))
        self.assertIn("Cleared", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self._handler()("unknown"))
        self.assertIn("Unknown subcommand", result)


class TestRetroCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q337_cmds import register_q337_commands
        reg = _FakeRegistry()
        register_q337_commands(reg)
        return reg.commands["retro"][1]

    def test_no_args_generates(self) -> None:
        result = _run(self._handler()(""))
        self.assertIn("Retrospective", result)

    def test_well(self) -> None:
        result = _run(self._handler()("well Good test coverage"))
        self.assertIn("Added:", result)

    def test_well_no_text(self) -> None:
        result = _run(self._handler()("well"))
        self.assertIn("Usage:", result)

    def test_improve(self) -> None:
        result = _run(self._handler()("improve Slow code review"))
        self.assertIn("Added:", result)

    def test_improve_no_text(self) -> None:
        result = _run(self._handler()("improve"))
        self.assertIn("Usage:", result)

    def test_action(self) -> None:
        result = _run(self._handler()("action Fix CI --assignee ops"))
        self.assertIn("Action added", result)
        self.assertIn("ops", result)

    def test_action_no_text(self) -> None:
        result = _run(self._handler()("action"))
        self.assertIn("Usage:", result)

    def test_generate_with_title(self) -> None:
        result = _run(self._handler()('generate --title "Sprint 5"'))
        self.assertIn("Sprint 5", result)

    def test_clear(self) -> None:
        result = _run(self._handler()("clear"))
        self.assertIn("Cleared", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self._handler()("unknown"))
        self.assertIn("Unknown subcommand", result)


if __name__ == "__main__":
    unittest.main()
