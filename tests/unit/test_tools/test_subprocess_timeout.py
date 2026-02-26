"""Regression tests: subprocesses must be killed when asyncio timeout fires.

Before the fix:
- BashTool caught TimeoutError but never killed the process → process leak
- GitTool had NO try/except at all → TimeoutError propagated uncaught, process leaked
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.bash import BashTool
from lidco.tools.git import GitTool


def _make_proc(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0) -> MagicMock:
    """Return a mock subprocess.Process."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    return proc


# ---------------------------------------------------------------------------
# BashTool — timeout
# ---------------------------------------------------------------------------


class TestBashToolTimeout:
    @pytest.mark.asyncio
    async def test_kills_process_on_timeout(self) -> None:
        """process.kill() must be called when communicate() times out."""
        proc = _make_proc()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        with patch("asyncio.create_subprocess_shell", return_value=proc):
            result = await BashTool().execute(command="sleep 9999", timeout=1)

        proc.kill.assert_called_once()
        assert result.success is False

    @pytest.mark.asyncio
    async def test_timeout_result_contains_duration(self) -> None:
        """Error message should mention the configured timeout value."""
        proc = _make_proc()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        with patch("asyncio.create_subprocess_shell", return_value=proc):
            result = await BashTool().execute(command="sleep 9999", timeout=42)

        assert "42s" in result.error
        assert result.success is False

    @pytest.mark.asyncio
    async def test_normal_execution_unaffected(self) -> None:
        """Happy path still returns stdout after the fix."""
        proc = _make_proc(stdout=b"hello\n", returncode=0)
        with patch("asyncio.create_subprocess_shell", return_value=proc):
            result = await BashTool().execute(command="echo hello")

        assert result.success is True
        assert "hello" in result.output
        proc.kill.assert_not_called()

    @pytest.mark.asyncio
    async def test_nonzero_exit_still_returns_result(self) -> None:
        """Non-zero exit code is reported as a ToolResult, not an exception."""
        proc = _make_proc(stdout=b"", stderr=b"not found\n", returncode=127)
        with patch("asyncio.create_subprocess_shell", return_value=proc):
            result = await BashTool().execute(command="missing-cmd")

        assert result.success is False
        assert result.metadata["exit_code"] == 127


# ---------------------------------------------------------------------------
# GitTool — timeout
# ---------------------------------------------------------------------------


class TestGitToolTimeout:
    @pytest.mark.asyncio
    async def test_kills_process_on_timeout(self) -> None:
        """process.kill() must be called when the git command times out."""
        proc = _make_proc()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        with patch("asyncio.create_subprocess_shell", return_value=proc):
            result = await GitTool().execute(command="log --oneline")

        proc.kill.assert_called_once()
        assert result.success is False

    @pytest.mark.asyncio
    async def test_timeout_result_mentions_60s(self) -> None:
        """Error message must mention the 60-second hard timeout."""
        proc = _make_proc()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        with patch("asyncio.create_subprocess_shell", return_value=proc):
            result = await GitTool().execute(command="log")

        assert "60s" in result.error
        assert result.metadata["exit_code"] == -1

    @pytest.mark.asyncio
    async def test_os_error_returns_result_not_exception(self) -> None:
        """OSError (e.g. git not on PATH) must return ToolResult, not propagate."""
        with patch(
            "asyncio.create_subprocess_shell",
            side_effect=OSError("git binary not found"),
        ):
            result = await GitTool().execute(command="status")

        assert result.success is False
        assert "git binary not found" in result.error
        assert result.metadata["exit_code"] == -1

    @pytest.mark.asyncio
    async def test_normal_execution_unaffected(self) -> None:
        """Happy path returns stdout after the fix."""
        proc = _make_proc(stdout=b"* main\n", returncode=0)
        with patch("asyncio.create_subprocess_shell", return_value=proc):
            result = await GitTool().execute(command="branch")

        assert result.success is True
        assert "main" in result.output
        proc.kill.assert_not_called()

    @pytest.mark.asyncio
    async def test_git_error_exit_code_reported(self) -> None:
        """Non-zero exit code is captured as ToolResult (not exception)."""
        proc = _make_proc(
            stderr=b"not a git repository\n", returncode=128
        )
        with patch("asyncio.create_subprocess_shell", return_value=proc):
            result = await GitTool().execute(command="status")

        assert result.success is False
        assert result.metadata["exit_code"] == 128
        assert "not_a_git_repo" in result.metadata.get("git_error_type", "")
