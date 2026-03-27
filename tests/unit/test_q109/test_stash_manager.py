"""Tests for src/lidco/git/stash_manager.py (mocked subprocess)."""
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lidco.git.stash_manager import StashEntry, StashManager, StashResult


def _make_proc(stdout="", stderr="", returncode=0):
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


_STASH_LIST_OUTPUT = """\
stash@{0}: On main: WIP auth fix
stash@{1}: On feature/login: Add login page
stash@{2}: On main: quick save
"""


class TestStashEntry:
    def test_name_is_ref(self):
        e = StashEntry(index=0, message="WIP", branch="main", ref="stash@{0}")
        assert e.name == "stash@{0}"

    def test_str_format(self):
        e = StashEntry(index=0, message="WIP", branch="main", ref="stash@{0}")
        s = str(e)
        assert "stash@{0}" in s
        assert "WIP" in s


class TestStashManager:
    def test_list_parses_output(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc(_STASH_LIST_OUTPUT)):
            entries = mgr.list()
        assert len(entries) == 3
        assert entries[0].message == "WIP auth fix"
        assert entries[0].branch == "main"

    def test_list_empty(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("")):
            entries = mgr.list()
        assert entries == []

    def test_list_error_returns_empty(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("", "fatal", 128)):
            entries = mgr.list()
        assert entries == []

    def test_push_success(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("Saved working directory")):
            with patch.object(mgr, "list", return_value=[
                StashEntry(0, "my msg", "main", "stash@{0}")
            ]):
                result = mgr.push(message="my msg")
        assert result.success is True
        assert result.entry is not None

    def test_push_failure(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("", "No local changes", 1)):
            result = mgr.push()
        assert result.success is False

    def test_pop_success(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("HEAD is now...")):
            result = mgr.pop(0)
        assert result.success is True

    def test_pop_failure(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("", "error", 1)):
            result = mgr.pop()
        assert result.success is False

    def test_apply_success(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("Applied")):
            result = mgr.apply("stash@{0}")
        assert result.success is True

    def test_drop_success(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("Dropped stash@{0}")):
            result = mgr.drop(0)
        assert result.success is True

    def test_drop_failure(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("", "error", 1)):
            result = mgr.drop(0)
        assert result.success is False

    def test_show_success(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("file.py | 3 +++")):
            output = mgr.show(0)
        assert "file.py" in output

    def test_show_failure_returns_stderr(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("", "error: bad ref", 1)):
            output = mgr.show(0)
        assert "error" in output.lower()

    def test_clear_success(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc("")):
            result = mgr.clear()
        assert result.success is True

    def test_count(self):
        mgr = StashManager()
        with patch.object(mgr, "list", return_value=[
            StashEntry(0, "a", "main", "stash@{0}"),
            StashEntry(1, "b", "dev", "stash@{1}"),
        ]):
            assert mgr.count() == 2

    def test_get_by_index(self):
        mgr = StashManager()
        with patch.object(mgr, "list", return_value=[
            StashEntry(0, "first", "main", "stash@{0}"),
            StashEntry(1, "second", "main", "stash@{1}"),
        ]):
            entry = mgr.get(1)
        assert entry is not None
        assert entry.message == "second"

    def test_get_not_found(self):
        mgr = StashManager()
        with patch.object(mgr, "list", return_value=[]):
            assert mgr.get(0) is None

    def test_summary(self):
        mgr = StashManager()
        with patch.object(mgr, "list", return_value=[
            StashEntry(0, "msg", "main", "stash@{0}")
        ]):
            s = mgr.summary()
        assert s["count"] == 1
        assert len(s["stashes"]) == 1

    def test_git_not_found_raises(self):
        mgr = StashManager(git_executable="nonexistent_git_xyz")
        from lidco.git.stash_manager import StashError
        with pytest.raises(StashError):
            mgr._run("stash", "list")

    def test_parse_stash_index(self):
        mgr = StashManager()
        with patch.object(mgr, "_run", return_value=_make_proc(_STASH_LIST_OUTPUT)):
            entries = mgr.list()
        assert entries[0].index == 0
        assert entries[1].index == 1
        assert entries[2].index == 2
