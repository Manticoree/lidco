"""Tests for T610 HooksManager."""
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lidco.git.hooks_manager import (
    GitHook,
    HookResult,
    HooksManager,
    STANDARD_HOOKS,
    _make_executable,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hooks_dir(tmp_path):
    d = tmp_path / ".git" / "hooks"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def manager(tmp_path, hooks_dir):
    return HooksManager(repo_root=str(tmp_path), hooks_dir=str(hooks_dir))


# ---------------------------------------------------------------------------
# _make_executable
# ---------------------------------------------------------------------------

class TestMakeExecutable:
    def test_sets_executable_bit(self, tmp_path):
        import sys
        f = tmp_path / "script.sh"
        f.write_text("#!/bin/sh\necho hello\n")
        _make_executable(f)
        if sys.platform != "win32":
            mode = f.stat().st_mode
            assert mode & stat.S_IXUSR
        else:
            # Windows doesn't support Unix executable bits via stat
            assert f.exists()  # just verify file still exists


# ---------------------------------------------------------------------------
# STANDARD_HOOKS
# ---------------------------------------------------------------------------

class TestStandardHooks:
    def test_pre_commit_in_standard(self):
        assert "pre-commit" in STANDARD_HOOKS

    def test_pre_push_in_standard(self):
        assert "pre-push" in STANDARD_HOOKS

    def test_commit_msg_in_standard(self):
        assert "commit-msg" in STANDARD_HOOKS


# ---------------------------------------------------------------------------
# HooksManager.list
# ---------------------------------------------------------------------------

class TestList:
    def test_empty_hooks_dir(self, manager):
        assert manager.list() == []

    def test_lists_enabled_hook(self, manager, hooks_dir):
        hook_file = hooks_dir / "pre-commit"
        hook_file.write_text("#!/bin/sh\nexit 0\n")
        hooks = manager.list()
        assert len(hooks) == 1
        assert hooks[0].name == "pre-commit"
        assert hooks[0].enabled is True

    def test_lists_disabled_hook(self, manager, hooks_dir):
        hook_file = hooks_dir / "pre-commit.disabled"
        hook_file.write_text("#!/bin/sh\nexit 0\n")
        hooks = manager.list()
        assert len(hooks) == 1
        assert hooks[0].enabled is False

    def test_skips_sample_files(self, manager, hooks_dir):
        (hooks_dir / "pre-commit.sample").write_text("#!/bin/sh\n")
        assert manager.list() == []

    def test_is_standard_flag(self, manager, hooks_dir):
        (hooks_dir / "pre-commit").write_text("#!/bin/sh\nexit 0\n")
        hooks = manager.list()
        assert hooks[0].is_standard is True

    def test_custom_hook_not_standard(self, manager, hooks_dir):
        (hooks_dir / "my-custom-hook").write_text("#!/bin/sh\nexit 0\n")
        hooks = manager.list()
        assert hooks[0].is_standard is False

    def test_no_hooks_dir_returns_empty(self, tmp_path):
        manager = HooksManager(repo_root=str(tmp_path), hooks_dir=str(tmp_path / "nonexistent"))
        assert manager.list() == []


# ---------------------------------------------------------------------------
# HooksManager.install
# ---------------------------------------------------------------------------

class TestInstall:
    def test_installs_hook(self, manager, hooks_dir):
        hook = manager.install("pre-commit", "exit 0")
        assert hook.name == "pre-commit"
        assert hook.enabled is True
        assert (hooks_dir / "pre-commit").exists()

    def test_adds_shebang(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 0")
        content = (hooks_dir / "pre-commit").read_text()
        assert content.startswith("#!/")

    def test_preserves_existing_shebang(self, manager, hooks_dir):
        manager.install("pre-commit", "#!/usr/bin/env bash\nexit 0")
        content = (hooks_dir / "pre-commit").read_text()
        assert content.startswith("#!/usr/bin/env bash")

    def test_raises_on_existing_no_overwrite(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 0")
        with pytest.raises(FileExistsError):
            manager.install("pre-commit", "exit 1")

    def test_overwrite_flag(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 0")
        manager.install("pre-commit", "exit 1", overwrite=True)
        content = (hooks_dir / "pre-commit").read_text()
        assert "exit 1" in content

    def test_creates_hooks_dir(self, tmp_path):
        custom_dir = tmp_path / "custom_hooks"
        manager = HooksManager(repo_root=str(tmp_path), hooks_dir=str(custom_dir))
        manager.install("pre-commit", "exit 0")
        assert custom_dir.is_dir()


# ---------------------------------------------------------------------------
# HooksManager.remove
# ---------------------------------------------------------------------------

class TestRemove:
    def test_removes_enabled_hook(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 0")
        result = manager.remove("pre-commit")
        assert result is True
        assert not (hooks_dir / "pre-commit").exists()

    def test_removes_disabled_hook(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 0")
        manager.disable("pre-commit")
        result = manager.remove("pre-commit")
        assert result is True

    def test_nonexistent_returns_false(self, manager):
        assert manager.remove("nonexistent") is False


# ---------------------------------------------------------------------------
# HooksManager.enable / disable
# ---------------------------------------------------------------------------

class TestEnableDisable:
    def test_disable_enabled_hook(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 0")
        hook = manager.disable("pre-commit")
        assert hook.enabled is False
        assert (hooks_dir / "pre-commit.disabled").exists()
        assert not (hooks_dir / "pre-commit").exists()

    def test_enable_disabled_hook(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 0")
        manager.disable("pre-commit")
        hook = manager.enable("pre-commit")
        assert hook.enabled is True
        assert (hooks_dir / "pre-commit").exists()
        assert not (hooks_dir / "pre-commit.disabled").exists()

    def test_disable_nonexistent_raises(self, manager):
        with pytest.raises(FileNotFoundError):
            manager.disable("nonexistent")

    def test_enable_nonexistent_raises(self, manager):
        with pytest.raises(FileNotFoundError):
            manager.enable("nonexistent")

    def test_disable_already_disabled_raises(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 0")
        manager.disable("pre-commit")
        with pytest.raises(ValueError):
            manager.disable("pre-commit")


# ---------------------------------------------------------------------------
# HooksManager.run
# ---------------------------------------------------------------------------

class TestRun:
    def test_run_success(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 0")
        with patch("lidco.git.hooks_manager.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
            result = manager.run("pre-commit")
        assert result.success is True
        assert result.returncode == 0

    def test_run_failure(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 1")
        with patch("lidco.git.hooks_manager.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            result = manager.run("pre-commit")
        assert result.success is False

    def test_run_not_installed(self, manager):
        result = manager.run("nonexistent")
        assert result.success is False
        assert result.returncode == -1
        assert "not installed" in result.stderr

    def test_run_disabled_hook(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 0")
        manager.disable("pre-commit")
        result = manager.run("pre-commit")
        assert result.success is False
        assert "disabled" in result.stderr

    def test_run_timeout(self, manager, hooks_dir):
        import subprocess
        manager.install("pre-commit", "sleep 100")
        with patch("lidco.git.hooks_manager.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            result = manager.run("pre-commit", timeout=5)
        assert result.success is False
        assert "timed out" in result.stderr

    def test_hook_result_output(self):
        result = HookResult("pre-commit", True, 0, stdout="hello\n", stderr="")
        assert "hello" in result.output


# ---------------------------------------------------------------------------
# HooksManager.get
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing(self, manager, hooks_dir):
        manager.install("pre-commit", "exit 0")
        hook = manager.get("pre-commit")
        assert hook is not None
        assert hook.name == "pre-commit"

    def test_get_nonexistent(self, manager):
        assert manager.get("nonexistent") is None


# ---------------------------------------------------------------------------
# install_from_config
# ---------------------------------------------------------------------------

class TestInstallFromConfig:
    def test_installs_multiple(self, manager, hooks_dir):
        hooks = manager.install_from_config({
            "pre-commit": "exit 0",
            "pre-push": "exit 0",
        })
        assert len(hooks) == 2
        names = {h.name for h in hooks}
        assert "pre-commit" in names
        assert "pre-push" in names
