"""Tests for Task 399 — DockerSandbox (src/lidco/tools/docker_sandbox.py)."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lidco.tools.docker_sandbox import DockerSandbox, DockerSandboxTool, SandboxResult


# ── SandboxResult ────────────────────────────────────────────────────────────

class TestSandboxResult:
    def test_fields(self):
        r = SandboxResult(stdout="out", stderr="err", returncode=0, elapsed=1.5)
        assert r.stdout == "out"
        assert r.returncode == 0
        assert r.elapsed == 1.5

    def test_frozen(self):
        r = SandboxResult(stdout="x", stderr="", returncode=0, elapsed=0.0)
        with pytest.raises((AttributeError, TypeError)):
            r.stdout = "y"  # type: ignore[misc]


# ── DockerSandbox.is_available ────────────────────────────────────────────────

class TestDockerSandboxAvailability:
    def test_docker_found(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            sb = DockerSandbox()
            assert sb.is_available() is True

    def test_docker_not_found(self):
        with patch("shutil.which", return_value=None):
            sb = DockerSandbox()
            assert sb.is_available() is False


# ── DockerSandbox.run ─────────────────────────────────────────────────────────

class TestDockerSandboxRun:
    def test_not_available_returns_127(self):
        with patch("shutil.which", return_value=None):
            sb = DockerSandbox()
            result = sb.run("echo hello")
        assert result.returncode == 127
        assert "docker" in result.stderr.lower()

    def test_successful_run(self):
        mock_proc = MagicMock()
        mock_proc.stdout = "hello\n"
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/docker"), \
             patch("subprocess.run", return_value=mock_proc) as mock_run:
            sb = DockerSandbox()
            result = sb.run("echo hello")
        assert result.returncode == 0
        assert result.stdout == "hello\n"
        # Verify --network none was passed
        call_args = mock_run.call_args[0][0]
        assert "--network" in call_args
        assert "none" in call_args

    def test_timeout_returns_124(self):
        with patch("shutil.which", return_value="/usr/bin/docker"), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 10)):
            sb = DockerSandbox()
            result = sb.run("sleep 100", timeout=10)
        assert result.returncode == 124
        assert "timed out" in result.stderr

    def test_file_not_found_returns_127(self):
        with patch("shutil.which", return_value="/usr/bin/docker"), \
             patch("subprocess.run", side_effect=FileNotFoundError("docker")):
            sb = DockerSandbox()
            result = sb.run("echo hi")
        assert result.returncode == 127

    def test_custom_image(self):
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/docker"), \
             patch("subprocess.run", return_value=mock_proc) as mock_run:
            sb = DockerSandbox(image="ubuntu:22.04")
            sb.run("ls")
        call_args = mock_run.call_args[0][0]
        assert "ubuntu:22.04" in call_args

    def test_generic_exception_returns_1(self):
        with patch("shutil.which", return_value="/usr/bin/docker"), \
             patch("subprocess.run", side_effect=RuntimeError("oops")):
            sb = DockerSandbox()
            result = sb.run("echo hi")
        assert result.returncode == 1


# ── DockerSandboxTool ─────────────────────────────────────────────────────────

class TestDockerSandboxTool:
    def test_name(self):
        assert DockerSandboxTool().name == "docker_sandbox"

    def test_description(self):
        desc = DockerSandboxTool().description.lower()
        assert "docker" in desc or "sandbox" in desc

    def test_parameters(self):
        params = {p.name for p in DockerSandboxTool().parameters}
        assert "command" in params

    def test_permission_ask(self):
        from lidco.tools.base import ToolPermission
        assert DockerSandboxTool().permission == ToolPermission.ASK

    @pytest.mark.asyncio
    async def test_execute_docker_unavailable(self):
        with patch("shutil.which", return_value=None):
            tool = DockerSandboxTool()
            result = await tool.execute(command="echo hi")
        assert not result.success
        assert "docker" in result.output.lower() or "Docker" in result.output

    @pytest.mark.asyncio
    async def test_execute_success(self):
        mock_proc = MagicMock()
        mock_proc.stdout = "sandbox_out\n"
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/docker"), \
             patch("subprocess.run", return_value=mock_proc):
            tool = DockerSandboxTool()
            result = await tool.execute(command="echo sandbox_out")
        assert result.success
        assert "sandbox_out" in result.output
