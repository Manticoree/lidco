"""Tests for PermissionManager — especially the git commit guard."""

from unittest.mock import MagicMock, patch

import pytest

from lidco.cli.permissions import PermissionManager
from lidco.core.config import PermissionsConfig


def _make_manager() -> PermissionManager:
    config = PermissionsConfig()
    console = MagicMock()
    return PermissionManager(config, console)


class TestIsGitCommit:
    def test_git_commit(self):
        assert PermissionManager._is_git_commit("git", {"command": "commit -m 'msg'"})

    def test_git_commit_bare(self):
        assert PermissionManager._is_git_commit("git", {"command": "commit"})

    def test_git_commit_amend(self):
        assert PermissionManager._is_git_commit("git", {"command": "commit --amend"})

    def test_git_status_is_not_commit(self):
        assert not PermissionManager._is_git_commit("git", {"command": "status"})

    def test_git_diff_is_not_commit(self):
        assert not PermissionManager._is_git_commit("git", {"command": "diff HEAD"})

    def test_bash_is_not_commit(self):
        assert not PermissionManager._is_git_commit("bash", {"command": "git commit -m 'x'"})

    def test_empty_command(self):
        assert not PermissionManager._is_git_commit("git", {"command": ""})

    def test_case_insensitive(self):
        assert PermissionManager._is_git_commit("git", {"command": "COMMIT -m 'msg'"})


class TestGitCommitAlwaysPrompts:
    """git commit must always prompt — even when git is session-allowed or allow_all is set."""

    def test_git_commit_prompts_when_session_allowed(self):
        mgr = _make_manager()
        mgr.auto_allow("git")  # git is session-allowed

        with patch("lidco.cli.permissions._run_permission_prompt", return_value="y") as mock_prompt:
            result = mgr.check("git", {"command": "commit -m 'feat: x'"})

        mock_prompt.assert_called_once()
        assert result is True

    def test_git_commit_prompts_when_allow_all(self):
        mgr = _make_manager()
        mgr.allow_all()

        with patch("lidco.cli.permissions._run_permission_prompt", return_value="y") as mock_prompt:
            result = mgr.check("git", {"command": "commit -m 'feat: x'"})

        mock_prompt.assert_called_once()
        assert result is True

    def test_git_commit_denied_when_user_says_no(self):
        mgr = _make_manager()

        with patch("lidco.cli.permissions._run_permission_prompt", return_value="n"):
            result = mgr.check("git", {"command": "commit -m 'feat: x'"})

        assert result is False

    def test_git_commit_allowed_once(self):
        mgr = _make_manager()

        with patch("lidco.cli.permissions._run_permission_prompt", return_value="y"):
            result = mgr.check("git", {"command": "commit -m 'feat: x'"})

        assert result is True

    def test_git_commit_prompts_every_time(self):
        """Two separate git commits must each show a prompt."""
        mgr = _make_manager()

        with patch("lidco.cli.permissions._run_permission_prompt", return_value="y") as mock_prompt:
            mgr.check("git", {"command": "commit -m 'first'"})
            mgr.check("git", {"command": "commit -m 'second'"})

        assert mock_prompt.call_count == 2


class TestNonCommitGitHonorsSessionAllow:
    """Non-commit git operations still respect session-allow shortcuts."""

    def test_git_status_skips_prompt_when_session_allowed(self):
        mgr = _make_manager()
        mgr.auto_allow("git")

        with patch("lidco.cli.permissions._run_permission_prompt") as mock_prompt:
            result = mgr.check("git", {"command": "status"})

        mock_prompt.assert_not_called()
        assert result is True

    def test_git_diff_skips_prompt_when_allow_all(self):
        mgr = _make_manager()
        mgr.allow_all()

        with patch("lidco.cli.permissions._run_permission_prompt") as mock_prompt:
            result = mgr.check("git", {"command": "diff HEAD"})

        mock_prompt.assert_not_called()
        assert result is True
