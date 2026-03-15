"""Tests for Task 396 — CodeRunner (src/lidco/tools/code_runner.py)."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lidco.tools.code_runner import CodeRunner, CodeRunnerTool, RunResult


# ── RunResult dataclass ──────────────────────────────────────────────────────

class TestRunResult:
    def test_fields_accessible(self):
        r = RunResult(stdout="out", stderr="err", returncode=0, elapsed=1.0, language="python")
        assert r.stdout == "out"
        assert r.stderr == "err"
        assert r.returncode == 0
        assert r.elapsed == 1.0
        assert r.language == "python"

    def test_frozen(self):
        r = RunResult(stdout="x", stderr="", returncode=0, elapsed=0.1, language="bash")
        with pytest.raises((AttributeError, TypeError)):
            r.stdout = "y"  # type: ignore[misc]


# ── CodeRunner.run_python ────────────────────────────────────────────────────

class TestCodeRunnerPython:
    def test_simple_print(self):
        runner = CodeRunner()
        result = runner.run_python("print('hello')")
        assert result.returncode == 0
        assert "hello" in result.stdout
        assert result.language == "python"
        assert result.elapsed >= 0

    def test_expression_with_assignment(self):
        runner = CodeRunner()
        result = runner.run_python("x = 1 + 1\nprint(x)")
        assert result.returncode == 0
        assert "2" in result.stdout

    def test_exception_captured(self):
        runner = CodeRunner()
        result = runner.run_python("raise ValueError('boom')")
        assert result.returncode == 1
        assert "ValueError" in result.stderr

    def test_syntax_error_captured(self):
        runner = CodeRunner()
        result = runner.run_python("def broken(")
        assert result.returncode == 1

    def test_isolated_namespace(self):
        runner = CodeRunner()
        # Each run has its own namespace, no leakage
        runner.run_python("secret = 42")
        result = runner.run_python("print(type(secret))")  # type: ignore[name-defined]
        assert result.returncode == 1  # NameError expected

    def test_stdout_captured(self):
        runner = CodeRunner()
        result = runner.run_python("import sys; sys.stdout.write('direct')")
        assert "direct" in result.stdout

    def test_stderr_captured(self):
        runner = CodeRunner()
        result = runner.run_python("import sys; sys.stderr.write('err_msg')")
        assert "err_msg" in result.stderr

    def test_returncode_zero_on_success(self):
        runner = CodeRunner()
        result = runner.run_python("pass")
        assert result.returncode == 0


# ── CodeRunner.run_bash ──────────────────────────────────────────────────────

class TestCodeRunnerBash:
    def test_success(self):
        mock_proc = MagicMock()
        mock_proc.stdout = "hello\n"
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            runner = CodeRunner()
            result = runner.run_bash("echo hello")
        assert result.returncode == 0
        assert result.stdout == "hello\n"
        assert result.language == "bash"
        mock_run.assert_called_once()

    def test_failure_returncode(self):
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        mock_proc.stderr = "cmd not found"
        mock_proc.returncode = 127
        with patch("subprocess.run", return_value=mock_proc):
            runner = CodeRunner()
            result = runner.run_bash("nonexistent_cmd_xyz")
        assert result.returncode == 127

    def test_timeout_returns_124(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            runner = CodeRunner()
            result = runner.run_bash("sleep 100", timeout=5)
        assert result.returncode == 124
        assert "timed out" in result.stderr

    def test_exception_returns_1(self):
        with patch("subprocess.run", side_effect=OSError("no shell")):
            runner = CodeRunner()
            result = runner.run_bash("echo hi")
        assert result.returncode == 1


# ── CodeRunner.run_js ────────────────────────────────────────────────────────

class TestCodeRunnerJs:
    def test_node_not_found(self):
        with patch("shutil.which", return_value=None):
            runner = CodeRunner()
            result = runner.run_js("console.log(1)")
        assert result.returncode == 127
        assert "node not found" in result.stderr
        assert result.language == "js"

    def test_node_success(self):
        mock_proc = MagicMock()
        mock_proc.stdout = "42\n"
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/node"), \
             patch("subprocess.run", return_value=mock_proc):
            runner = CodeRunner()
            result = runner.run_js("console.log(42)")
        assert result.returncode == 0
        assert "42" in result.stdout

    def test_node_timeout(self):
        with patch("shutil.which", return_value="/usr/bin/node"), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("node", 5)):
            runner = CodeRunner()
            result = runner.run_js("while(true){}", timeout=5)
        assert result.returncode == 124


# ── CodeRunnerTool ───────────────────────────────────────────────────────────

class TestCodeRunnerTool:
    def test_name(self):
        assert CodeRunnerTool().name == "code_runner"

    def test_description(self):
        assert "Python" in CodeRunnerTool().description or "python" in CodeRunnerTool().description.lower()

    def test_parameters(self):
        params = {p.name for p in CodeRunnerTool().parameters}
        assert "language" in params
        assert "code" in params

    def test_permission_ask(self):
        from lidco.tools.base import ToolPermission
        assert CodeRunnerTool().permission == ToolPermission.ASK

    @pytest.mark.asyncio
    async def test_execute_python(self):
        tool = CodeRunnerTool()
        result = await tool.execute(language="python", code="print('test_out')")
        assert result.success
        assert "test_out" in result.output

    @pytest.mark.asyncio
    async def test_execute_unknown_language(self):
        tool = CodeRunnerTool()
        result = await tool.execute(language="cobol", code="DISPLAY 'hello'")
        assert not result.success

    @pytest.mark.asyncio
    async def test_execute_bash_mocked(self):
        mock_proc = MagicMock()
        mock_proc.stdout = "mocked\n"
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch("subprocess.run", return_value=mock_proc):
            tool = CodeRunnerTool()
            result = await tool.execute(language="bash", code="echo mocked")
        assert result.success
        assert "mocked" in result.output
