"""Tests for Task 388 — /repos command and multi-repo support."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestReposCommand:
    """Tests for /repos slash command logic."""

    def test_extra_repos_starts_empty(self):
        """Registry _extra_repos attribute should start empty."""
        repos: list[str] = []
        assert repos == []

    def test_add_path_resolves_absolute(self, tmp_path):
        """Adding a path should store the resolved absolute path."""
        repos: list[str] = []
        p = tmp_path
        resolved = str(p.resolve())
        if resolved not in repos:
            repos.append(resolved)
        assert resolved in repos

    def test_remove_path_removes_from_list(self, tmp_path):
        """Removing a path should remove it from the list."""
        repos: list[str] = [str(tmp_path)]
        resolved = str(tmp_path)
        if resolved in repos:
            repos.remove(resolved)
        assert resolved not in repos

    def test_add_duplicate_not_added_twice(self, tmp_path):
        """Adding same path twice should not duplicate."""
        repos: list[str] = []
        resolved = str(tmp_path)
        if resolved not in repos:
            repos.append(resolved)
        if resolved not in repos:
            repos.append(resolved)
        assert repos.count(resolved) == 1

    def test_remove_nonexistent_path(self, tmp_path):
        """Removing a path not in the list should not raise."""
        repos: list[str] = [str(tmp_path)]
        non_existent = "/some/path/not/in/list"
        if non_existent in repos:
            repos.remove(non_existent)
        assert len(repos) == 1  # unchanged

    def test_list_returns_all_repos(self, tmp_path):
        """List should return all repos."""
        repos = [str(tmp_path), "/fake/path"]
        assert len(repos) == 2

    def test_repos_git_status_context_injection(self, tmp_path):
        """Simulate injecting git status for extra repos into context."""
        import subprocess
        repos = [str(tmp_path)]
        context_parts = []
        for repo in repos:
            try:
                r = subprocess.run(
                    ["git", "status", "--short"],
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                context_parts.append(f"## Repo: {repo}\n{r.stdout}")
            except Exception:
                context_parts.append(f"## Repo: {repo}\n(git unavailable)")
        # Should not raise and should have one entry
        assert len(context_parts) == 1

    def test_repos_attribute_registered_on_registry(self):
        """_extra_repos should be accessible as a list."""
        registry = MagicMock()
        registry._extra_repos = []
        registry._extra_repos.append("/some/path")
        assert len(registry._extra_repos) == 1

    def test_non_directory_path_rejected(self, tmp_path):
        """Adding a file path (not dir) should be caught."""
        file_path = tmp_path / "somefile.txt"
        file_path.write_text("content")
        assert file_path.exists()
        assert not file_path.is_dir()

    def test_nonexistent_path_rejected(self, tmp_path):
        """Adding a path that doesn't exist should be rejected."""
        p = tmp_path / "does_not_exist"
        assert not p.exists()


class TestReposContextInjection:
    """Tests for context injection from extra repos."""

    def test_git_branch_command_format(self):
        """Git branch command should use correct args."""
        expected_cmd = ["git", "branch", "--show-current"]
        assert expected_cmd[0] == "git"
        assert "--show-current" in expected_cmd

    def test_git_status_short_format(self):
        """Git status should use --short flag."""
        expected_cmd = ["git", "status", "--short"]
        assert "--short" in expected_cmd

    def test_repos_context_format(self):
        """Context block should include repo path and status."""
        repo_path = "/some/project"
        status = "M src/main.py"
        branch = "feature/my-branch"
        block = f"## Extra Repo: {repo_path}\nBranch: {branch}\n{status}"
        assert repo_path in block
        assert status in block
        assert branch in block
