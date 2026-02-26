"""Tests for RunTestsTool and its parsing helpers."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.test_runner import (
    RunTestsTool,
    _extract_coverage_summary,
    _extract_failed_tests,
    _extract_failure_section,
    _parse_summary,
    _stream_lines,
)


# ---------------------------------------------------------------------------
# Helper parsers
# ---------------------------------------------------------------------------

class TestParseSummary:
    def test_all_passed(self) -> None:
        out = "5 passed in 0.12s"
        assert _parse_summary(out) == (5, 0, 0, 0)

    def test_mixed_results(self) -> None:
        out = "3 passed, 2 failed, 1 error, 4 skipped in 1.5s"
        assert _parse_summary(out) == (3, 2, 1, 4)

    def test_only_failed(self) -> None:
        out = "7 failed in 3.0s"
        assert _parse_summary(out) == (0, 7, 0, 0)

    def test_no_tests(self) -> None:
        out = "no tests ran"
        assert _parse_summary(out) == (0, 0, 0, 0)

    def test_picks_last_matching_line(self) -> None:
        out = "collecting ... collected 10 items\n\n10 passed in 0.5s"
        assert _parse_summary(out) == (10, 0, 0, 0)


class TestExtractFailedTests:
    def test_single_failure(self) -> None:
        out = "FAILED tests/unit/test_foo.py::TestFoo::test_bar"
        assert _extract_failed_tests(out) == ["tests/unit/test_foo.py::TestFoo::test_bar"]

    def test_multiple_failures(self) -> None:
        out = (
            "FAILED tests/a.py::test_one\n"
            "FAILED tests/b.py::test_two - AssertionError: boom\n"
        )
        result = _extract_failed_tests(out)
        assert result == ["tests/a.py::test_one", "tests/b.py::test_two"]

    def test_no_failures(self) -> None:
        out = "5 passed in 0.1s"
        assert _extract_failed_tests(out) == []

    def test_strips_error_message(self) -> None:
        out = "FAILED path/to/test.py::test_x - ValueError: oops"
        result = _extract_failed_tests(out)
        assert result == ["path/to/test.py::test_x"]


class TestExtractCoverageSummary:
    def test_extracts_table(self) -> None:
        out = (
            "---------- coverage ----------\n"
            "Name                     Stmts   Miss  Cover\n"
            "--------------------------------------------\n"
            "src/lidco/foo.py            10      2    80%\n"
            "TOTAL                       10      2    80%\n"
        )
        result = _extract_coverage_summary(out)
        assert "Stmts" in result
        assert "TOTAL" in result

    def test_no_coverage(self) -> None:
        out = "5 passed in 0.1s"
        assert _extract_coverage_summary(out) == ""


class TestExtractFailureSection:
    def test_extracts_failures_block(self) -> None:
        out = (
            "collected 2 items\n\n"
            "========================= FAILURES =========================\n"
            "_____ test_foo _____\n"
            "AssertionError: expected 1 got 2\n"
            "========================= 1 failed =========================\n"
        )
        result = _extract_failure_section(out)
        assert "FAILURES" in result
        assert "AssertionError" in result

    def test_no_failure_section(self) -> None:
        out = "5 passed in 0.1s"
        assert _extract_failure_section(out) == ""


# ---------------------------------------------------------------------------
# RunTestsTool._run()
# ---------------------------------------------------------------------------

def _make_process(stdout: str, stderr: str = "", returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(
        return_value=(stdout.encode(), stderr.encode())
    )
    return proc


class TestRunTestsTool:
    def setup_method(self) -> None:
        self.tool = RunTestsTool()

    # --- metadata ---
    def test_name(self) -> None:
        assert self.tool.name == "run_tests"

    def test_has_five_parameters(self) -> None:
        names = {p.name for p in self.tool.parameters}
        assert names == {"test_path", "verbose", "coverage", "timeout", "stream_output"}

    # --- happy path ---
    @pytest.mark.asyncio
    async def test_all_passed_returns_success(self) -> None:
        proc = _make_process("5 passed in 0.2s\n", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run()
        assert result.success is True
        assert "5 passed" in result.output
        assert result.metadata["passed"] == 5
        assert result.metadata["failed"] == 0

    @pytest.mark.asyncio
    async def test_failures_reported_correctly(self) -> None:
        stdout = (
            "FAILED tests/unit/test_x.py::test_alpha\n"
            "1 failed in 0.3s\n"
        )
        proc = _make_process(stdout, returncode=1)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run()
        assert result.success is False
        assert "1 failed" in result.output
        assert "test_alpha" in result.output
        assert result.metadata["failed_tests"] == ["tests/unit/test_x.py::test_alpha"]

    @pytest.mark.asyncio
    async def test_test_path_passed_to_pytest(self) -> None:
        proc = _make_process("1 passed in 0.1s\n", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await self.tool._run(test_path="tests/unit/test_foo.py")
        cmd = mock_exec.call_args[0]
        assert "tests/unit/test_foo.py" in cmd

    @pytest.mark.asyncio
    async def test_verbose_flag(self) -> None:
        proc = _make_process("1 passed\n", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await self.tool._run(verbose=True)
        cmd = mock_exec.call_args[0]
        assert "-v" in cmd
        assert "-q" not in cmd

    @pytest.mark.asyncio
    async def test_coverage_flag(self) -> None:
        proc = _make_process("1 passed\n", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await self.tool._run(coverage=True)
        cmd = mock_exec.call_args[0]
        assert "--cov" in cmd

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self) -> None:
        proc = _make_process("")
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(timeout=1)
        assert result.success is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_pytest_not_found_returns_error(self) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await self.tool._run()
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_stderr_included_in_output(self) -> None:
        proc = _make_process("0 passed\n", stderr="WARNING: something weird\n", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run()
        assert "WARNING" in result.output

    @pytest.mark.asyncio
    async def test_output_truncated_at_15k(self) -> None:
        long_out = "x" * 20000 + "\n1 passed\n"
        proc = _make_process(long_out, returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run()
        assert len(result.output) < 15500

    # --- stream_output=False still uses communicate() ---
    @pytest.mark.asyncio
    async def test_stream_false_uses_communicate(self) -> None:
        proc = _make_process("3 passed\n", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(stream_output=False)
        proc.communicate.assert_awaited_once()
        assert result.success is True

    # --- stream_output=True without callback falls back to communicate() ---
    @pytest.mark.asyncio
    async def test_stream_true_without_callback_uses_communicate(self) -> None:
        proc = _make_process("2 passed\n", returncode=0)
        # no progress_callback set — must fall back to communicate()
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(stream_output=True)
        proc.communicate.assert_awaited_once()
        assert result.success is True


# ---------------------------------------------------------------------------
# _stream_lines helper
# ---------------------------------------------------------------------------

def _make_streaming_process(lines: list[str], returncode: int = 0) -> MagicMock:
    """Build a mock async subprocess that yields *lines* from readline()."""
    proc = MagicMock()
    proc.returncode = returncode

    encoded = [l.encode() for l in lines] + [b""]  # final b"" signals EOF

    async def _readline() -> bytes:
        return encoded.pop(0)

    stdout_mock = MagicMock()
    stdout_mock.readline = _readline
    proc.stdout = stdout_mock

    stderr_mock = MagicMock()
    stderr_mock.read = AsyncMock(return_value=b"")
    proc.stderr = stderr_mock

    proc.wait = AsyncMock()
    return proc


class TestStreamLines:
    @pytest.mark.asyncio
    async def test_calls_callback_for_each_line(self) -> None:
        lines = ["line one\n", "line two\n", "3 passed\n"]
        proc = _make_streaming_process(lines, returncode=0)
        received: list[str] = []
        stdout_text, stderr_text = await _stream_lines(proc, received.append, timeout=5)
        assert received == ["line one", "line two", "3 passed"]
        assert "line one\n" in stdout_text
        assert stderr_text == ""

    @pytest.mark.asyncio
    async def test_returns_full_stdout(self) -> None:
        lines = ["a\n", "b\n"]
        proc = _make_streaming_process(lines, returncode=0)
        stdout_text, _ = await _stream_lines(proc, lambda _: None, timeout=5)
        assert stdout_text == "a\nb\n"

    @pytest.mark.asyncio
    async def test_strips_newline_from_callback_arg(self) -> None:
        proc = _make_streaming_process(["hello\n"], returncode=0)
        received: list[str] = []
        await _stream_lines(proc, received.append, timeout=5)
        assert received == ["hello"]

    @pytest.mark.asyncio
    async def test_timeout_returns_partial_and_waits(self) -> None:
        """On timeout _stream_lines must NOT raise — it returns partial output
        and always calls process.wait() so the process is properly reaped."""
        import asyncio as _asyncio

        proc = MagicMock()
        proc.stdout = MagicMock()
        # readline blocks forever → asyncio.wait_for triggers TimeoutError
        proc.stdout.readline = AsyncMock(side_effect=_asyncio.TimeoutError)
        proc.stderr = MagicMock()
        proc.stderr.read = AsyncMock(return_value=b"some stderr\n")
        proc.wait = AsyncMock()

        # Must not raise
        stdout_text, stderr_text = await _stream_lines(proc, lambda _: None, timeout=1)

        # process.wait() must always be called so the process is reaped
        proc.wait.assert_called_once()
        # stderr must be read even on timeout
        assert "some stderr" in stderr_text


class TestRunTestsToolStreaming:
    def setup_method(self) -> None:
        self.tool = RunTestsTool()

    @pytest.mark.asyncio
    async def test_stream_output_calls_callback_per_line(self) -> None:
        lines = ["collecting ...\n", "PASSED test_x\n", "1 passed in 0.1s\n"]
        proc = _make_streaming_process(lines, returncode=0)
        received: list[str] = []
        self.tool.set_progress_callback(received.append)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(stream_output=True)

        assert "1 passed" in result.output
        assert result.success is True
        # callback received at least the summary line
        assert any("1 passed" in line for line in received)

    @pytest.mark.asyncio
    async def test_stream_output_does_not_use_communicate(self) -> None:
        lines = ["1 passed\n"]
        proc = _make_streaming_process(lines, returncode=0)
        self.tool.set_progress_callback(lambda _: None)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await self.tool._run(stream_output=True)

        # communicate() should NOT have been called
        proc.communicate.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_progress_callback_stores_value(self) -> None:
        cb = lambda line: None  # noqa: E731
        self.tool.set_progress_callback(cb)
        assert self.tool._progress_callback is cb

    @pytest.mark.asyncio
    async def test_set_progress_callback_none_clears_value(self) -> None:
        self.tool.set_progress_callback(lambda _: None)
        self.tool.set_progress_callback(None)
        assert self.tool._progress_callback is None
