"""Tests for lidco exec headless mode — Task 261."""

from __future__ import annotations

import asyncio
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lidco.cli.exec_mode import ExecFlags, PrecommitFlags, run_exec, run_precommit
from lidco.cli.exit_codes import (
    CONFIG_ERROR,
    INPUT_ERROR,
    SUCCESS,
    TASK_FAILED,
)


def _make_agent_response(content: str):
    """Create a mock AgentResponse."""
    r = MagicMock()
    r.content = content
    r.token_usage = MagicMock()
    r.token_usage.prompt_tokens = 0
    r.token_usage.completion_tokens = 0
    r.token_usage.total_tokens = 0
    return r


def _make_session(response="Task completed."):
    """Create a mock Session with orchestrator."""
    session = MagicMock()
    session.config = MagicMock()
    session.config.llm.default_model = "test-model"
    session.config.llm.streaming = False
    session.config.agents.auto_plan = True
    session.config.agents.auto_review = True
    session.config.permissions.mode = "default"
    session.tool_registry = MagicMock()
    session.permission_engine = MagicMock()
    session.orchestrator = MagicMock()
    session.orchestrator.handle = AsyncMock(return_value=_make_agent_response(response))
    session.orchestrator.set_token_callback = MagicMock()
    session.orchestrator.set_tool_event_callback = MagicMock()
    session.orchestrator.set_permission_handler = MagicMock()
    session.orchestrator.set_continue_handler = MagicMock()
    session.orchestrator.set_status_callback = MagicMock()
    session.get_full_context = MagicMock(return_value="")
    session._config_reloader = MagicMock()
    session._config_reloader.stop = MagicMock()
    return session


class TestExecFlagsDataclass:
    def test_defaults(self):
        f = ExecFlags()
        assert f.task == ""
        assert f.json is False
        assert f.quiet is False
        assert f.max_turns is None
        assert f.agent is None
        assert f.no_plan is False

    def test_with_task(self):
        f = ExecFlags(task="fix tests", json=True)
        assert f.task == "fix tests"
        assert f.json is True


class TestRunExecInputError:
    @pytest.mark.asyncio
    async def test_no_task_no_stdin_returns_input_error(self):
        flags = ExecFlags(task="", quiet=True)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            code = await run_exec(flags)
        assert code == INPUT_ERROR

    @pytest.mark.asyncio
    async def test_empty_stdin_returns_input_error(self):
        flags = ExecFlags(task="", quiet=True)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = "   "
            code = await run_exec(flags)
        assert code == INPUT_ERROR


class TestRunExecSuccess:
    @pytest.mark.asyncio
    async def test_task_success_returns_zero(self):
        flags = ExecFlags(task="do something", quiet=True)
        session = _make_session(response="Done successfully.")

        with patch("lidco.cli.exec_mode.Session", return_value=session), \
             patch("lidco.cli.exec_mode.load_config", return_value=session.config):
            code = await run_exec(flags)

        assert code == SUCCESS

    @pytest.mark.asyncio
    async def test_empty_response_is_task_failed(self):
        flags = ExecFlags(task="do something", quiet=True)
        session = _make_session(response="")

        with patch("lidco.cli.exec_mode.Session", return_value=session), \
             patch("lidco.cli.exec_mode.load_config", return_value=session.config):
            code = await run_exec(flags)

        assert code == TASK_FAILED

    @pytest.mark.asyncio
    async def test_json_output_calls_print_json(self, capsys):
        flags = ExecFlags(task="fix tests", json=True, quiet=True)
        session = _make_session(response="Tests fixed.")

        with patch("lidco.cli.exec_mode.Session", return_value=session), \
             patch("lidco.cli.exec_mode.load_config", return_value=session.config):
            code = await run_exec(flags)

        import json
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "success"
        assert data["exit_code"] == 0
        assert "tokens" in data
        assert "changes" in data

    @pytest.mark.asyncio
    async def test_plain_output_printed(self, capsys):
        flags = ExecFlags(task="explain foo", quiet=False)
        session = _make_session(response="Here is the explanation.")

        with patch("lidco.cli.exec_mode.Session", return_value=session), \
             patch("lidco.cli.exec_mode.load_config", return_value=session.config):
            await run_exec(flags)

        captured = capsys.readouterr()
        assert "explanation" in captured.out

    @pytest.mark.asyncio
    async def test_agent_flag_passed_to_orchestrator(self):
        flags = ExecFlags(task="task", agent="security", quiet=True)
        session = _make_session(response="Security review done.")

        with patch("lidco.cli.exec_mode.Session", return_value=session), \
             patch("lidco.cli.exec_mode.load_config", return_value=session.config):
            await run_exec(flags)

        call_kwargs = session.orchestrator.handle.call_args
        assert call_kwargs[1]["agent_name"] == "security"

    @pytest.mark.asyncio
    async def test_exception_returns_task_failed(self):
        flags = ExecFlags(task="task", quiet=True)
        session = _make_session(response="")
        session.orchestrator.handle = AsyncMock(side_effect=RuntimeError("LLM error"))

        with patch("lidco.cli.exec_mode.Session", return_value=session), \
             patch("lidco.cli.exec_mode.load_config", return_value=session.config):
            code = await run_exec(flags)

        assert code == TASK_FAILED

    @pytest.mark.asyncio
    async def test_stdin_task_read_when_no_arg(self):
        flags = ExecFlags(task="", quiet=True)
        session = _make_session(response="Done.")

        with patch("lidco.cli.exec_mode.Session", return_value=session), \
             patch("lidco.cli.exec_mode.load_config", return_value=session.config), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = "task from stdin"
            code = await run_exec(flags)

        assert code == SUCCESS

    @pytest.mark.asyncio
    async def test_config_load_failure_returns_config_error(self):
        flags = ExecFlags(task="fix", quiet=True)

        with patch("lidco.cli.exec_mode.load_config", side_effect=Exception("no config")):
            code = await run_exec(flags)

        assert code == CONFIG_ERROR


class TestPrecommitFlags:
    def test_defaults(self):
        f = PrecommitFlags()
        assert f.agent is None
        assert f.json is False
        assert f.max_turns is None


class TestRunPrecommit:
    @pytest.mark.asyncio
    async def test_no_staged_files_returns_success(self):
        flags = PrecommitFlags(quiet=True)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            code = await run_precommit(flags)
        assert code == SUCCESS

    @pytest.mark.asyncio
    async def test_staged_files_trigger_exec(self):
        flags = PrecommitFlags(quiet=True)
        session = _make_session(response="No critical issues found.")

        with patch("subprocess.run") as mock_run, \
             patch("lidco.cli.exec_mode.Session", return_value=session), \
             patch("lidco.cli.exec_mode.load_config", return_value=session.config):
            mock_run.return_value = MagicMock(stdout="src/auth.py\nsrc/api.py\n", returncode=0)
            code = await run_precommit(flags)

        assert code == SUCCESS
        # Verify the task mentioned the staged files
        call_args = session.orchestrator.handle.call_args
        task_text = call_args[0][0]
        assert "auth.py" in task_text or "staged" in task_text.lower()
