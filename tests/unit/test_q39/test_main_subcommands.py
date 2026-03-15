"""Tests for __main__.py subcommand parsing — Task 261, 263."""

from __future__ import annotations

import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestExecSubcommand:
    def test_exec_no_args_shows_usage(self, capsys):
        """exec with no task and interactive stdin returns INPUT_ERROR."""
        with patch("sys.argv", ["lidco", "exec"]), \
             patch("sys.stdin") as mock_stdin, \
             patch("sys.exit") as mock_exit, \
             patch("asyncio.run", return_value=5):  # INPUT_ERROR = 5
            mock_stdin.isatty.return_value = True
            from lidco.__main__ import main
            try:
                main()
            except SystemExit:
                pass
            mock_exit.assert_called_with(5)

    def test_exec_with_task_calls_asyncio_run(self):
        with patch("sys.argv", ["lidco", "exec", "fix all tests"]), \
             patch("asyncio.run", return_value=0) as mock_run, \
             patch("sys.exit"):
            from lidco.__main__ import _run_exec
            _run_exec(["fix all tests"])
            mock_run.assert_called_once()

    def test_exec_json_flag_parsed(self):
        """--json flag triggers asyncio.run without error."""
        from lidco.__main__ import _run_exec
        with patch("asyncio.run", return_value=0) as mock_run, \
             patch("sys.exit"):
            _run_exec(["--json", "mytask"])
            mock_run.assert_called_once()

    def test_exec_max_turns_flag_parsed(self):
        from lidco.__main__ import _run_exec
        with patch("asyncio.run", return_value=0) as mock_run, \
             patch("sys.exit"):
            _run_exec(["--max-turns", "5", "task"])
        mock_run.assert_called_once()

    def test_exec_invalid_max_turns_exits_config_error(self):
        from lidco.__main__ import _run_exec
        from lidco.cli.exit_codes import CONFIG_ERROR
        with patch("sys.exit") as mock_exit, \
             patch("asyncio.run", return_value=0):
            _run_exec(["--max-turns", "notanint", "task"])
        # First sys.exit call should be CONFIG_ERROR
        first_call_arg = mock_exit.call_args_list[0][0][0]
        assert first_call_arg == CONFIG_ERROR


class TestPrecommitSubcommand:
    def test_precommit_no_args_calls_asyncio_run(self):
        with patch("sys.argv", ["lidco", "precommit"]), \
             patch("asyncio.run", return_value=0) as mock_run, \
             patch("sys.exit"):
            from lidco.__main__ import _run_precommit
            _run_precommit([])
            mock_run.assert_called_once()

    def test_precommit_json_flag_parsed(self):
        from lidco.__main__ import _run_precommit
        with patch("asyncio.run", return_value=0), \
             patch("sys.exit"):
            _run_precommit(["--json"])  # Should not raise


class TestHelpFlag:
    def test_help_flag_exits_zero(self, capsys):
        with patch("sys.argv", ["lidco", "--help"]), \
             pytest.raises(SystemExit) as exc_info:
            from lidco.__main__ import main
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "exec" in captured.out
        assert "precommit" in captured.out
