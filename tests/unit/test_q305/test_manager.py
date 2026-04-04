"""Tests for HookManagerV2."""

import os
import stat
from unittest.mock import patch, MagicMock

import pytest

from lidco.githooks.manager import HookManagerV2, HookResult, HookType


class TestHookType:
    def test_enum_values(self):
        assert HookType.PRE_COMMIT.value == "pre-commit"
        assert HookType.PRE_PUSH.value == "pre-push"
        assert HookType.COMMIT_MSG.value == "commit-msg"
        assert HookType.POST_COMMIT.value == "post-commit"

    def test_enum_count(self):
        assert len(HookType) == 4


class TestHookResult:
    def test_frozen(self):
        r = HookResult(hook_type=HookType.PRE_COMMIT, success=True, exit_code=0)
        with pytest.raises(AttributeError):
            r.success = False  # type: ignore[misc]

    def test_defaults(self):
        r = HookResult(hook_type=HookType.PRE_COMMIT, success=True, exit_code=0)
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.duration == 0.0


class TestHookManagerV2:
    def _make(self, tmp_path):
        return HookManagerV2(hooks_dir=tmp_path / "hooks")

    def test_hooks_dir_created(self, tmp_path):
        d = tmp_path / "hooks"
        assert not d.exists()
        mgr = HookManagerV2(hooks_dir=d)
        assert d.exists()
        assert mgr.hooks_dir == d

    def test_install_creates_file(self, tmp_path):
        mgr = self._make(tmp_path)
        result = mgr.install(HookType.PRE_COMMIT, "#!/bin/sh\nexit 0")
        assert result is True
        path = mgr.hooks_dir / "pre-commit"
        assert path.exists()
        assert "exit 0" in path.read_text()

    def test_install_makes_executable(self, tmp_path):
        mgr = self._make(tmp_path)
        mgr.install(HookType.PRE_COMMIT, "#!/bin/sh\nexit 0")
        path = mgr.hooks_dir / "pre-commit"
        assert path.exists()
        # On Unix the executable bit is set; on Windows chmod is a no-op
        # so we just verify the file was written correctly
        if os.name != "nt":
            mode = path.stat().st_mode
            assert mode & stat.S_IEXEC

    def test_uninstall_existing(self, tmp_path):
        mgr = self._make(tmp_path)
        mgr.install(HookType.PRE_COMMIT, "#!/bin/sh\nexit 0")
        assert mgr.uninstall(HookType.PRE_COMMIT) is True
        assert not (mgr.hooks_dir / "pre-commit").exists()

    def test_uninstall_missing_returns_false(self, tmp_path):
        mgr = self._make(tmp_path)
        assert mgr.uninstall(HookType.PRE_PUSH) is False

    def test_list_installed_empty(self, tmp_path):
        mgr = self._make(tmp_path)
        assert mgr.list_installed() == []

    def test_list_installed_returns_types(self, tmp_path):
        mgr = self._make(tmp_path)
        mgr.install(HookType.PRE_COMMIT, "#!/bin/sh\nexit 0")
        mgr.install(HookType.POST_COMMIT, "#!/bin/sh\nexit 0")
        installed = mgr.list_installed()
        assert HookType.PRE_COMMIT in installed
        assert HookType.POST_COMMIT in installed
        assert len(installed) == 2

    def test_run_not_installed(self, tmp_path):
        mgr = self._make(tmp_path)
        result = mgr.run(HookType.PRE_COMMIT)
        assert result.success is False
        assert result.exit_code == -1
        assert "not installed" in result.stderr.lower()

    @patch("lidco.githooks.manager.subprocess.run")
    def test_run_success(self, mock_run, tmp_path):
        mgr = self._make(tmp_path)
        mgr.install(HookType.PRE_COMMIT, "#!/bin/sh\nexit 0")
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        result = mgr.run(HookType.PRE_COMMIT)
        assert result.success is True
        assert result.exit_code == 0

    @patch("lidco.githooks.manager.subprocess.run")
    def test_run_failure(self, mock_run, tmp_path):
        mgr = self._make(tmp_path)
        mgr.install(HookType.PRE_COMMIT, "#!/bin/sh\nexit 1")
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="bad")
        result = mgr.run(HookType.PRE_COMMIT)
        assert result.success is False
        assert result.exit_code == 1

    @patch("lidco.githooks.manager.subprocess.run")
    def test_parallel_run(self, mock_run, tmp_path):
        mgr = self._make(tmp_path)
        mgr.install(HookType.PRE_COMMIT, "#!/bin/sh\nexit 0")
        mgr.install(HookType.POST_COMMIT, "#!/bin/sh\nexit 0")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        results = mgr.parallel_run([HookType.PRE_COMMIT, HookType.POST_COMMIT])
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_parallel_run_empty(self, tmp_path):
        mgr = self._make(tmp_path)
        assert mgr.parallel_run([]) == []

    @patch("lidco.githooks.manager.subprocess.run")
    def test_run_timeout(self, mock_run, tmp_path):
        import subprocess as sp
        mgr = self._make(tmp_path)
        mgr.install(HookType.PRE_COMMIT, "#!/bin/sh\nsleep 999")
        mock_run.side_effect = sp.TimeoutExpired(cmd="hook", timeout=60)
        result = mgr.run(HookType.PRE_COMMIT)
        assert result.success is False
        assert result.exit_code == -2
        assert "timed out" in result.stderr.lower()

    @patch("lidco.githooks.manager.subprocess.run")
    def test_run_os_error(self, mock_run, tmp_path):
        mgr = self._make(tmp_path)
        mgr.install(HookType.PRE_COMMIT, "#!/bin/sh\nexit 0")
        mock_run.side_effect = OSError("Permission denied")
        result = mgr.run(HookType.PRE_COMMIT)
        assert result.success is False
        assert result.exit_code == -3
