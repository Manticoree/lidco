"""Tests for ContainerSandbox (T526)."""
from unittest.mock import MagicMock, patch

import pytest

from lidco.tools.container_sandbox import ContainerConfig, ContainerResult, ContainerSandbox


@pytest.fixture
def sandbox(tmp_path):
    config = ContainerConfig(repo_path=str(tmp_path))
    return ContainerSandbox(config)


# ---- docker availability ----

def test_docker_not_available_returns_error(sandbox):
    with patch.object(ContainerSandbox, "_docker_available", return_value=False):
        result = sandbox.run("echo hello")
    assert result.exit_code == 1
    assert "Docker not available" in result.stderr


# ---- run with docker available ----

def _mock_subprocess_run(returncode=0, stdout="ok", stderr=""):
    mock = MagicMock()
    mock.returncode = returncode
    mock.stdout = stdout
    mock.stderr = stderr
    return mock


def test_run_success(sandbox, tmp_path):
    with patch.object(ContainerSandbox, "_docker_available", return_value=True), \
         patch("subprocess.run", return_value=_mock_subprocess_run(0, "output")), \
         patch.object(sandbox, "get_diff", return_value=""):
        result = sandbox.run("echo hello")
    assert result.exit_code == 0
    assert result.stdout == "output"
    assert isinstance(result.duration, float)


def test_run_failure_exit_code(sandbox):
    with patch.object(ContainerSandbox, "_docker_available", return_value=True), \
         patch("subprocess.run", return_value=_mock_subprocess_run(1, "", "error")), \
         patch.object(sandbox, "get_diff", return_value=""):
        result = sandbox.run("false")
    assert result.exit_code == 1
    assert result.stderr == "error"


def test_run_timeout(sandbox):
    import subprocess
    with patch.object(ContainerSandbox, "_docker_available", return_value=True), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 5)):
        result = sandbox.run("sleep 100")
    assert result.exit_code == 124
    assert "timed out" in result.stderr


def test_run_exception_caught(sandbox):
    with patch.object(ContainerSandbox, "_docker_available", return_value=True), \
         patch("subprocess.run", side_effect=OSError("docker missing")):
        result = sandbox.run("echo hi")
    assert result.exit_code == 1
    assert "docker missing" in result.stderr


# ---- docker args ----

def test_network_disabled_flag(sandbox):
    captured = []
    def fake_run(args, **kwargs):
        captured.append(args)
        return _mock_subprocess_run()
    with patch.object(ContainerSandbox, "_docker_available", return_value=True), \
         patch("subprocess.run", side_effect=fake_run), \
         patch.object(sandbox, "get_diff", return_value=""):
        sandbox.run("echo")
    assert "--network" in captured[0]
    assert "none" in captured[0]


def test_memory_limit_flag(tmp_path):
    config = ContainerConfig(repo_path=str(tmp_path), memory_limit_mb=256)
    s = ContainerSandbox(config)
    captured = []
    def fake_run(args, **kwargs):
        captured.append(args)
        return _mock_subprocess_run()
    with patch.object(ContainerSandbox, "_docker_available", return_value=True), \
         patch("subprocess.run", side_effect=fake_run), \
         patch.object(s, "get_diff", return_value=""):
        s.run("echo")
    assert any("256m" in str(a) for a in captured[0])


# ---- get_diff ----

def test_get_diff_returns_string(sandbox, tmp_path):
    with patch("subprocess.run", return_value=_mock_subprocess_run(0, "diff output")):
        diff = sandbox.get_diff()
    assert diff == "diff output"


def test_get_diff_exception_returns_empty(sandbox):
    with patch("subprocess.run", side_effect=Exception("no git")):
        diff = sandbox.get_diff()
    assert diff == ""


# ---- config ----

def test_default_config():
    s = ContainerSandbox()
    assert s._config.image == "python:3.13-slim"
    assert s._config.network_disabled is True
    assert s._config.memory_limit_mb == 512


# ---- cleanup ----

def test_cleanup_no_container_no_error(sandbox):
    sandbox.cleanup()  # should not raise


def test_cleanup_calls_docker_rm(sandbox):
    sandbox._container_id = "abc123"
    with patch("subprocess.run") as mock_run:
        sandbox.cleanup()
    assert mock_run.called
    assert sandbox._container_id is None
