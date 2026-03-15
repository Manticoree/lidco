"""Tests for Q59 slash commands in commands.py."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.cli.commands import CommandRegistry, SlashCommand


def make_registry() -> CommandRegistry:
    """Create a CommandRegistry with no session."""
    return CommandRegistry()


# ── /run command (Task 396) ───────────────────────────────────────────────────

class TestRunCommand:
    def test_run_registered(self):
        reg = make_registry()
        cmd = reg.get("run")
        assert cmd is not None
        assert cmd.name == "run"

    @pytest.mark.asyncio
    async def test_run_no_arg_returns_usage(self):
        reg = make_registry()
        cmd = reg.get("run")
        result = await cmd.handler(arg="")
        assert "Usage" in result or "usage" in result.lower()

    @pytest.mark.asyncio
    async def test_run_python_executes(self):
        reg = make_registry()
        cmd = reg.get("run")
        result = await cmd.handler(arg="python print('hello_test')")
        assert "hello_test" in result

    @pytest.mark.asyncio
    async def test_run_bash_mocked(self):
        mock_proc = MagicMock()
        mock_proc.stdout = "bash_output\n"
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch("subprocess.run", return_value=mock_proc):
            reg = make_registry()
            cmd = reg.get("run")
            result = await cmd.handler(arg="bash echo bash_output")
        assert "bash_output" in result or "bash" in result.lower()

    @pytest.mark.asyncio
    async def test_run_detects_language_token(self):
        reg = make_registry()
        cmd = reg.get("run")
        # "python" prefix should be detected
        result = await cmd.handler(arg="python 1+1")
        assert "[python]" in result

    @pytest.mark.asyncio
    async def test_run_defaults_to_python(self):
        reg = make_registry()
        cmd = reg.get("run")
        result = await cmd.handler(arg="print('default')")
        assert "default" in result


# ── /debug run extension (Task 397) ───────────────────────────────────────────

class TestDebugRunCommand:
    def test_debug_registered(self):
        reg = make_registry()
        cmd = reg.get("debug")
        assert cmd is not None

    @pytest.mark.asyncio
    async def test_debug_run_no_file_returns_usage(self):
        reg = make_registry()
        cmd = reg.get("debug")
        result = await cmd.handler(arg="run")
        assert "Usage" in result or "usage" in result.lower()

    @pytest.mark.asyncio
    async def test_debug_run_syntax_error(self):
        import subprocess as _sp
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        mock_proc.stderr = "SyntaxError: invalid syntax"
        mock_proc.returncode = 1
        with patch("subprocess.run", return_value=mock_proc):
            reg = make_registry()
            cmd = reg.get("debug")
            result = await cmd.handler(arg="run bad_file.py")
        assert "Syntax error" in result or "syntax" in result.lower()

    @pytest.mark.asyncio
    async def test_debug_on_still_works(self):
        reg = make_registry()
        mock_session = MagicMock()
        mock_session.debug_mode = False
        mock_orch = MagicMock()
        mock_session.orchestrator = mock_orch
        reg.set_session(mock_session)
        cmd = reg.get("debug")
        # Calling /debug on should still work
        result = await cmd.handler(arg="on")
        assert result  # Should return something

    @pytest.mark.asyncio
    async def test_debug_run_success(self):
        """Test /debug run with a file that runs successfully."""
        import asyncio

        # Syntax check returns OK
        mock_syntax = MagicMock()
        mock_syntax.stdout = ""
        mock_syntax.stderr = ""
        mock_syntax.returncode = 0

        # Mock the async subprocess execution
        mock_exec_proc = MagicMock()
        mock_exec_proc.returncode = 0
        mock_exec_proc.communicate = AsyncMock(return_value=(b"script output\n", b""))

        with patch("subprocess.run", return_value=mock_syntax), \
             patch("asyncio.create_subprocess_exec", return_value=mock_exec_proc):
            reg = make_registry()
            cmd = reg.get("debug")
            result = await cmd.handler(arg="run somefile.py")
        assert "script output" in result or "exit 0" in result


# ── /test command (Task 398) ──────────────────────────────────────────────────

class TestTestCommand:
    def test_test_registered(self):
        reg = make_registry()
        cmd = reg.get("test")
        assert cmd is not None
        assert cmd.name == "test"

    @pytest.mark.asyncio
    async def test_test_no_arg_returns_usage(self):
        reg = make_registry()
        cmd = reg.get("test")
        result = await cmd.handler(arg="")
        assert "Usage" in result or "pytest" in result.lower()

    @pytest.mark.asyncio
    async def test_test_runs_pytest(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"5 passed in 1.0s\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            reg = make_registry()
            cmd = reg.get("test")
            result = await cmd.handler(arg="tests/")
        assert "passed" in result.lower() or "pytest" in result.lower()

    @pytest.mark.asyncio
    async def test_test_failure_shows_failed(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"2 failed, 3 passed\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            reg = make_registry()
            cmd = reg.get("test")
            result = await cmd.handler(arg="tests/")
        assert "FAILED" in result or "failed" in result.lower()


# ── /venv command (Task 400) ──────────────────────────────────────────────────

class TestVenvCommand:
    def test_venv_registered(self):
        reg = make_registry()
        cmd = reg.get("venv")
        assert cmd is not None
        assert cmd.name == "venv"

    @pytest.mark.asyncio
    async def test_venv_list_empty(self, tmp_path):
        reg = make_registry()
        mock_session = MagicMock()
        mock_session.project_dir = tmp_path
        reg.set_session(mock_session)
        cmd = reg.get("venv")
        result = await cmd.handler(arg="list")
        assert "No virtual environments" in result or "venv" in result.lower()

    @pytest.mark.asyncio
    async def test_venv_create_no_name(self):
        reg = make_registry()
        cmd = reg.get("venv")
        result = await cmd.handler(arg="create")
        assert "Usage" in result or "name" in result.lower()

    @pytest.mark.asyncio
    async def test_venv_delete_not_found(self, tmp_path):
        reg = make_registry()
        mock_session = MagicMock()
        mock_session.project_dir = tmp_path
        reg.set_session(mock_session)
        cmd = reg.get("venv")
        result = await cmd.handler(arg="delete nonexistent_env")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_venv_activate_not_found(self, tmp_path):
        reg = make_registry()
        mock_session = MagicMock()
        mock_session.project_dir = tmp_path
        reg.set_session(mock_session)
        cmd = reg.get("venv")
        result = await cmd.handler(arg="activate nonexistent_env")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_venv_unknown_subcommand(self):
        reg = make_registry()
        cmd = reg.get("venv")
        result = await cmd.handler(arg="foobar")
        assert "Usage" in result or "venv" in result.lower()


# ── /install command (Task 401) ───────────────────────────────────────────────

class TestInstallCommand:
    def test_install_registered(self):
        reg = make_registry()
        cmd = reg.get("install")
        assert cmd is not None
        assert cmd.name == "install"

    @pytest.mark.asyncio
    async def test_install_no_arg_returns_usage(self):
        reg = make_registry()
        cmd = reg.get("install")
        result = await cmd.handler(arg="")
        assert "Usage" in result or "package" in result.lower()

    @pytest.mark.asyncio
    async def test_install_requires_confirm_by_default(self):
        reg = make_registry()
        cmd = reg.get("install")
        result = await cmd.handler(arg="requests")
        # Without --no-confirm, should show what will happen
        assert "--no-confirm" in result or "confirm" in result.lower() or "pip install" in result

    @pytest.mark.asyncio
    async def test_install_no_confirm_runs_pip(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"Successfully installed requests-2.31.0\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            reg = make_registry()
            cmd = reg.get("install")
            result = await cmd.handler(arg="requests --no-confirm")
        assert "install" in result.lower() or "requests" in result

    @pytest.mark.asyncio
    async def test_install_pip_failure(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"ERROR: Could not find version\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            reg = make_registry()
            cmd = reg.get("install")
            result = await cmd.handler(arg="badpackage999 --no-confirm")
        assert "failed" in result.lower() or "error" in result.lower() or "exit" in result.lower()


# ── /diff-output command (Task 402) ──────────────────────────────────────────

class TestDiffOutputCommand:
    def test_diff_output_registered(self):
        reg = make_registry()
        cmd = reg.get("diff-output")
        assert cmd is not None
        assert cmd.name == "diff-output"

    @pytest.mark.asyncio
    async def test_diff_output_no_arg_returns_usage(self):
        reg = make_registry()
        cmd = reg.get("diff-output")
        result = await cmd.handler(arg="")
        assert "Usage" in result or "command" in result.lower()

    @pytest.mark.asyncio
    async def test_diff_output_first_call_captures_baseline(self):
        mock_proc = MagicMock()
        mock_proc.stdout = "v1.0\n"
        mock_proc.returncode = 0
        with patch("subprocess.run", return_value=mock_proc):
            reg = make_registry()
            cmd = reg.get("diff-output")
            result = await cmd.handler(arg="myapp --version")
        assert "Baseline" in result or "baseline" in result.lower()

    @pytest.mark.asyncio
    async def test_diff_output_second_call_shows_diff(self):
        call_count = 0
        outputs = ["v1.0\n", "v2.0\n"]

        def fake_run(*args, **kwargs):
            nonlocal call_count
            m = MagicMock()
            m.stdout = outputs[call_count]
            m.returncode = 0
            call_count += 1
            return m

        with patch("subprocess.run", side_effect=fake_run):
            reg = make_registry()
            cmd = reg.get("diff-output")
            await cmd.handler(arg="myapp --version")
            result = await cmd.handler(arg="myapp --version")
        assert "diff" in result.lower() or "changed" in result.lower() or "lines" in result.lower()

    @pytest.mark.asyncio
    async def test_diff_output_no_change(self):
        mock_proc = MagicMock()
        mock_proc.stdout = "same output\n"
        mock_proc.returncode = 0

        with patch("subprocess.run", return_value=mock_proc):
            reg = make_registry()
            cmd = reg.get("diff-output")
            await cmd.handler(arg="stable_cmd")
            result = await cmd.handler(arg="stable_cmd")
        assert "No changes" in result or "no change" in result.lower()


# ── Registry integration ──────────────────────────────────────────────────────

class TestRegistryIntegration:
    def test_all_q59_commands_registered(self):
        reg = make_registry()
        expected = {"run", "debug", "test", "venv", "install", "diff-output"}
        registered = {cmd.name for cmd in reg.list_commands()}
        for name in expected:
            assert name in registered, f"Command /{name} not registered"

    def test_docker_sandbox_in_registry(self):
        from lidco.tools.registry import ToolRegistry
        reg = ToolRegistry.create_default_registry()
        assert reg.get("docker_sandbox") is not None

    def test_code_runner_in_registry(self):
        from lidco.tools.registry import ToolRegistry
        reg = ToolRegistry.create_default_registry()
        assert reg.get("code_runner") is not None
