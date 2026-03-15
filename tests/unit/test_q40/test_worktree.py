"""Tests for Q40 — WorktreeManager (Task 269)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from lidco.agents.worktree import WorktreeManager, WorktreeInfo


class TestWorktreeManagerCreate:
    def test_create_calls_git_worktree_add(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        with patch.object(mgr, "_git") as mock_git, \
             patch.object(Path, "mkdir"):
            result = mgr.create("abc123")
        expected_path = tmp_path / ".lidco" / "worktrees" / "abc123"
        mock_git.assert_called_once_with(
            "worktree", "add", str(expected_path), "-b", "lidco/abc123", "--no-track"
        )
        assert result == expected_path

    def test_create_returns_none_on_failure(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        with patch.object(mgr, "_git", side_effect=subprocess.CalledProcessError(1, "git")), \
             patch.object(Path, "mkdir"):
            result = mgr.create("fail123")
        assert result is None

    def test_create_returns_none_when_git_not_found(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        with patch.object(mgr, "_git", side_effect=FileNotFoundError()), \
             patch.object(Path, "mkdir"):
            result = mgr.create("nogit")
        assert result is None

    def test_create_stores_active_entry(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        with patch.object(mgr, "_git"), patch.object(Path, "mkdir"):
            mgr.create("agent1")
        assert "agent1" in mgr.list_active()
        info = mgr.list_active()["agent1"]
        assert info.agent_id == "agent1"
        assert info.branch == "lidco/agent1"


class TestWorktreeManagerHasChanges:
    def test_has_changes_returns_true_on_dirty(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        with patch.object(mgr, "_git_output", return_value="M  file.py\n"):
            assert mgr.has_changes(tmp_path) is True

    def test_has_changes_returns_false_on_clean(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        with patch.object(mgr, "_git_output", return_value=""):
            assert mgr.has_changes(tmp_path) is False

    def test_has_changes_returns_false_on_exception(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        with patch.object(mgr, "_git_output", side_effect=Exception("fail")):
            assert mgr.has_changes(tmp_path) is False


class TestWorktreeManagerFinish:
    def _setup_active(self, mgr: WorktreeManager, agent_id: str) -> WorktreeInfo:
        path = mgr._project_dir / ".lidco" / "worktrees" / agent_id
        info = WorktreeInfo(agent_id=agent_id, path=path, branch=f"lidco/{agent_id}")
        mgr._active[agent_id] = info
        return info

    def test_finish_no_changes_cleans_up(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        self._setup_active(mgr, "clean")
        with patch.object(mgr, "has_changes", return_value=False), \
             patch.object(mgr, "_git"):
            result = mgr.finish("clean")
        assert result is None
        assert "clean" not in mgr.list_active()

    def test_finish_with_changes_returns_branch(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        self._setup_active(mgr, "dirty")
        with patch.object(mgr, "has_changes", return_value=True), \
             patch.object(mgr, "_git"):
            result = mgr.finish("dirty")
        assert result == "lidco/dirty"
        assert "dirty" not in mgr.list_active()

    def test_finish_unknown_agent_returns_none(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        assert mgr.finish("nonexistent") is None

    def test_finish_removes_branch_when_no_changes(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        self._setup_active(mgr, "gone")
        git_calls: list = []
        with patch.object(mgr, "has_changes", return_value=False), \
             patch.object(mgr, "_git", side_effect=lambda *a: git_calls.append(a)):
            mgr.finish("gone")
        # Should call "worktree remove" and "branch -D"
        assert any(a[0] == "worktree" for a in git_calls)
        assert any(a[0] == "branch" for a in git_calls)


class TestWorktreeManagerRemove:
    def test_remove_force_removes(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        path = tmp_path / ".lidco" / "worktrees" / "x"
        mgr._active["x"] = WorktreeInfo(agent_id="x", path=path, branch="lidco/x")
        with patch.object(mgr, "_git"):
            mgr.remove("x")
        assert "x" not in mgr.list_active()

    def test_remove_nonexistent_is_noop(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        mgr.remove("nope")  # should not raise


class TestWorktreeManagerListActive:
    def test_list_active_returns_copy(self, tmp_path):
        mgr = WorktreeManager(tmp_path)
        path = tmp_path / ".lidco" / "worktrees" / "y"
        mgr._active["y"] = WorktreeInfo(agent_id="y", path=path, branch="lidco/y")
        active = mgr.list_active()
        assert "y" in active
        active.pop("y")
        assert "y" in mgr.list_active()  # original not mutated
