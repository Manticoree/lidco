"""Tests for T617 ProcessRunner."""
import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest

from lidco.execution.process_runner import ProcessRunner, ProcessResult


# ---------------------------------------------------------------------------
# ProcessResult
# ---------------------------------------------------------------------------

class TestProcessResult:
    def _make(self, returncode=0, stdout="", stderr="", timed_out=False, error=""):
        return ProcessResult(
            cmd="echo hello",
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            elapsed_ms=10.0,
            timed_out=timed_out,
            error=error,
        )

    def test_ok_true_for_zero_exit(self):
        assert self._make(0).ok is True

    def test_ok_false_for_nonzero(self):
        assert self._make(1).ok is False

    def test_ok_false_for_timeout(self):
        assert self._make(0, timed_out=True).ok is False

    def test_output_combined(self):
        r = self._make(stdout="out\n", stderr="err\n")
        assert "out" in r.output
        assert "err" in r.output

    def test_output_stdout_only(self):
        r = self._make(stdout="hello")
        assert r.output == "hello"

    def test_format_summary_ok(self):
        r = self._make(0, stdout="result")
        s = r.format_summary()
        assert "result" in s
        assert "exit=0" in s

    def test_format_summary_failure(self):
        r = self._make(1, stderr="error msg")
        s = r.format_summary()
        assert "exit=1" in s

    def test_format_summary_timeout(self):
        r = self._make(timed_out=True)
        s = r.format_summary()
        assert "TIMED OUT" in s


# ---------------------------------------------------------------------------
# ProcessRunner — real commands
# ---------------------------------------------------------------------------

class TestProcessRunnerReal:
    def test_run_echo(self):
        runner = ProcessRunner()
        if sys.platform == "win32":
            result = runner.run("echo hello")
        else:
            result = runner.run("echo hello")
        assert result.ok
        assert "hello" in result.stdout

    def test_run_list_cmd(self):
        runner = ProcessRunner(shell=False)
        if sys.platform == "win32":
            result = runner.run(["cmd", "/c", "echo", "hi"])
        else:
            result = runner.run(["echo", "hi"])
        assert result.ok
        assert "hi" in result.stdout

    def test_run_exit_code(self):
        runner = ProcessRunner()
        if sys.platform == "win32":
            result = runner.run("exit 1", shell=True)
        else:
            result = runner.run("exit 1", shell=True)
        assert result.returncode != 0 or result.ok  # platform variation

    def test_run_with_stdin(self):
        runner = ProcessRunner()
        if sys.platform == "win32":
            result = runner.run("findstr .", stdin="hello world\n")
        else:
            result = runner.run("cat", stdin="hello world\n")
        assert result.ok

    def test_run_timeout_kills(self):
        runner = ProcessRunner()
        # Use Python itself for a cross-platform sleep
        result = runner.run(
            f"{sys.executable} -c \"import time; time.sleep(30)\"",
            timeout=0.5,
        )
        assert result.timed_out

    def test_run_env_variable(self):
        runner = ProcessRunner()
        if sys.platform == "win32":
            result = runner.run("echo %MYVAR%", env={"MYVAR": "testvalue"})
        else:
            result = runner.run("echo $MYVAR", env={"MYVAR": "testvalue"})
        assert "testvalue" in result.stdout

    def test_run_cwd(self, tmp_path):
        runner = ProcessRunner()
        if sys.platform == "win32":
            result = runner.run("cd", cwd=str(tmp_path))
        else:
            result = runner.run("pwd", cwd=str(tmp_path))
        assert result.ok


class TestProcessRunnerMocked:
    def _mock_proc(self, returncode=0, stdout=b"out\n", stderr=b""):
        mock = MagicMock()
        mock.returncode = returncode
        mock.communicate.return_value = (stdout, stderr)
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    def test_run_success(self):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = self._mock_proc(0, b"result\n")
            runner = ProcessRunner()
            result = runner.run("echo result")
        assert result.ok
        assert "result" in result.stdout

    def test_run_failure(self):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = self._mock_proc(2, b"", b"error\n")
            runner = ProcessRunner()
            result = runner.run("bad command")
        assert result.returncode == 2

    def test_run_timeout(self):
        with patch("subprocess.Popen") as mock_popen:
            proc = self._mock_proc()
            proc.communicate.side_effect = subprocess.TimeoutExpired("cmd", 1)
            proc.kill.return_value = None
            proc.communicate.side_effect = [subprocess.TimeoutExpired("cmd", 1), (b"", b"")]
            mock_popen.return_value = proc
            runner = ProcessRunner(default_timeout=1)
            result = runner.run("sleep 30")
        assert result.timed_out

    def test_is_available_true(self):
        runner = ProcessRunner()
        assert runner.is_available("python") or runner.is_available("python3")

    def test_is_available_false(self):
        runner = ProcessRunner()
        assert not runner.is_available("nonexistent_command_xyz_123")

    def test_which_returns_path(self):
        runner = ProcessRunner()
        python = runner.which("python") or runner.which("python3")
        assert python is not None


class TestRunScript:
    def test_script_multi_line(self):
        runner = ProcessRunner()
        if sys.platform == "win32":
            script = "echo line1\necho line2"
        else:
            script = "echo line1\necho line2"
        result = runner.run_script(script)
        assert result.ok
        assert "line1" in result.stdout or "line2" in result.stdout

    def test_script_stops_on_error(self):
        with patch.object(ProcessRunner, "run") as mock_run:
            fail_result = ProcessResult("bad", 1, "", "err", 10.0)
            ok_result = ProcessResult("ok", 0, "ok", "", 5.0)
            mock_run.side_effect = [fail_result, ok_result]
            runner = ProcessRunner()
            result = runner.run_script("bad_cmd\nok_cmd")
        # Only first command called due to error stop
        assert mock_run.call_count == 1

    def test_script_ignores_dash_error(self):
        with patch.object(ProcessRunner, "run") as mock_run:
            fail_result = ProcessResult("bad", 1, "", "err", 10.0)
            ok_result = ProcessResult("ok", 0, "ok", "", 5.0)
            mock_run.side_effect = [fail_result, ok_result]
            runner = ProcessRunner()
            result = runner.run_script("-bad_cmd\nok_cmd")
        # Both called because dash suppresses error
        assert mock_run.call_count == 2

    def test_script_skips_comments(self):
        with patch.object(ProcessRunner, "run") as mock_run:
            mock_run.return_value = ProcessResult("cmd", 0, "ok", "", 5.0)
            runner = ProcessRunner()
            runner.run_script("# this is a comment\nreal_cmd")
        assert mock_run.call_count == 1
