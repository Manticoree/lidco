"""Tests for src/lidco/execution/terminal_capture.py."""

import sys
import pytest
from lidco.execution.terminal_capture import CaptureResult, TerminalCapture


def make_capture(**kwargs) -> TerminalCapture:
    return TerminalCapture(**kwargs)


class TestCaptureResultDataclass:
    def test_fields(self):
        r = CaptureResult(
            command="echo hi",
            stdout="hi\n",
            stderr="",
            returncode=0,
            elapsed_s=0.01,
        )
        assert r.command == "echo hi"
        assert r.returncode == 0
        assert r.elapsed_s == 0.01

    def test_success_true(self):
        r = CaptureResult("cmd", "out", "", 0, 0.1)
        assert r.success is True

    def test_success_false(self):
        r = CaptureResult("cmd", "", "err", 1, 0.1)
        assert r.success is False

    def test_combined_output_both(self):
        r = CaptureResult("cmd", "out\n", "err\n", 0, 0.1)
        assert "out" in r.combined_output
        assert "err" in r.combined_output

    def test_combined_output_stdout_only(self):
        r = CaptureResult("cmd", "stdout", "", 0, 0.1)
        assert r.combined_output == "stdout"

    def test_combined_output_empty(self):
        r = CaptureResult("cmd", "", "", 0, 0.1)
        assert r.combined_output == ""


class TestTerminalCaptureInit:
    def test_defaults(self):
        tc = TerminalCapture()
        assert tc.timeout == 30
        assert tc.max_output_bytes == 65536

    def test_custom(self):
        tc = TerminalCapture(timeout=5, max_output_bytes=1024)
        assert tc.timeout == 5
        assert tc.max_output_bytes == 1024


class TestRun:
    def test_successful_command(self):
        tc = TerminalCapture()
        # Use python -c so it works on all platforms
        result = tc.run(f'{sys.executable} -c "print(\'hello\')"')
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_failing_command(self):
        tc = TerminalCapture()
        result = tc.run(f'{sys.executable} -c "import sys; sys.exit(42)"')
        assert result.returncode == 42

    def test_elapsed_non_negative(self):
        tc = TerminalCapture()
        result = tc.run(f'{sys.executable} -c "pass"')
        assert result.elapsed_s >= 0

    def test_timeout_override(self):
        tc = TerminalCapture(timeout=60)
        result = tc.run(f'{sys.executable} -c "pass"', timeout=5)
        assert result.success

    def test_timeout_expired(self):
        tc = TerminalCapture(timeout=1)
        result = tc.run(
            f'{sys.executable} -c "import time; time.sleep(10)"', timeout=1
        )
        assert result.returncode == -1
        assert "timeout" in result.stderr
        assert result.timed_out is True  # B11

    def test_normal_failure_not_timed_out(self):
        tc = TerminalCapture()
        result = tc.run(f'{sys.executable} -c "import sys; sys.exit(1)"')
        assert result.timed_out is False  # B11

    def test_stderr_captured(self):
        tc = TerminalCapture()
        result = tc.run(
            f'{sys.executable} -c "import sys; sys.stderr.write(\'err\\n\')"'
        )
        assert "err" in result.stderr

    def test_command_stored(self):
        tc = TerminalCapture()
        cmd = f'{sys.executable} -c "pass"'
        result = tc.run(cmd)
        assert result.command == cmd


class TestTruncate:
    def test_no_truncation(self):
        tc = TerminalCapture(max_output_bytes=100)
        assert tc._truncate("hello") == "hello"

    def test_truncation_applied(self):
        tc = TerminalCapture(max_output_bytes=5)
        result = tc._truncate("A" * 20)
        assert "truncated" in result


class TestFormatForContext:
    def test_includes_command(self):
        tc = TerminalCapture()
        r = CaptureResult("ls -la", "file1\nfile2\n", "", 0, 0.05)
        formatted = tc.format_for_context(r)
        assert "ls -la" in formatted

    def test_includes_exit_code(self):
        tc = TerminalCapture()
        r = CaptureResult("cmd", "out", "", 0, 0.1)
        formatted = tc.format_for_context(r)
        assert "0" in formatted

    def test_includes_stdout(self):
        tc = TerminalCapture()
        r = CaptureResult("cmd", "my output", "", 0, 0.1)
        formatted = tc.format_for_context(r)
        assert "my output" in formatted

    def test_includes_stderr(self):
        tc = TerminalCapture()
        r = CaptureResult("cmd", "", "my error", 1, 0.1)
        formatted = tc.format_for_context(r)
        assert "my error" in formatted

    def test_no_stdout_section_when_empty(self):
        tc = TerminalCapture()
        r = CaptureResult("cmd", "", "err", 1, 0.1)
        formatted = tc.format_for_context(r)
        assert "stdout" not in formatted.lower() or "my output" not in formatted


class TestRunAndFormat:
    def test_returns_tuple(self):
        tc = TerminalCapture()
        result, formatted = tc.run_and_format(f'{sys.executable} -c "pass"')
        assert isinstance(result, CaptureResult)
        assert isinstance(formatted, str)

    def test_formatted_contains_command(self):
        tc = TerminalCapture()
        cmd = f'{sys.executable} -c "pass"'
        _, formatted = tc.run_and_format(cmd)
        assert cmd in formatted
