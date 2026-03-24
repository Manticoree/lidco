"""Tests for AutoCommitter — T446 auto-commit mode."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.git.auto_commit import AutoCommitResult, AutoCommitter


def make_committer(dirty_files=None, commit_ok=True):
    ac = AutoCommitter(project_dir=Path("/fake"))
    ac.enable()

    def fake_run(*args):
        cp = MagicMock(spec=subprocess.CompletedProcess)
        cp.returncode = 0
        if "status" in args:
            cp.stdout = "\n".join(f" M {f}" for f in (dirty_files or [])) + "\n"
        elif "commit" in args:
            cp.returncode = 0 if commit_ok else 1
            cp.stdout = "[main abc1234] msg\n"
            cp.stderr = "error" if not commit_ok else ""
        elif "rev-parse" in args:
            cp.stdout = "abc1234\n"
        else:
            cp.stdout = ""
        return cp

    ac._run = lambda *a: fake_run(*a)
    return ac


class TestAutoCommitterToggle:
    def test_starts_disabled(self):
        ac = AutoCommitter()
        assert not ac.enabled

    def test_enable(self):
        ac = AutoCommitter()
        ac.enable()
        assert ac.enabled

    def test_disable(self):
        ac = AutoCommitter()
        ac.enable()
        ac.disable()
        assert not ac.enabled

    def test_toggle_on(self):
        ac = AutoCommitter()
        result = ac.toggle()
        assert result is True
        assert ac.enabled

    def test_toggle_off(self):
        ac = AutoCommitter()
        ac.enable()
        result = ac.toggle()
        assert result is False
        assert not ac.enabled


class TestCommitIfDirty:
    def test_disabled_returns_no_commit(self):
        ac = AutoCommitter()
        r = ac.commit_if_dirty("some work")
        assert not r.committed
        assert r.commit_hash is None

    def test_nothing_to_commit(self):
        ac = make_committer(dirty_files=[])
        r = ac.commit_if_dirty("work done")
        assert not r.committed
        assert "nothing" in r.message

    def test_commits_dirty_files(self):
        ac = make_committer(dirty_files=["foo.py", "bar.py"])
        r = ac.commit_if_dirty("fix: update foo and bar")
        assert r.committed
        assert r.commit_hash is not None
        assert "foo.py" in r.files_staged

    def test_long_description_truncated(self):
        ac = make_committer(dirty_files=["a.py"])
        long_desc = "x" * 100
        r = ac.commit_if_dirty(long_desc)
        assert len(r.message) <= 72

    def test_short_description_unchanged(self):
        ac = make_committer(dirty_files=["a.py"])
        r = ac.commit_if_dirty("fix: short message")
        assert r.message == "fix: short message"

    def test_commit_failure(self):
        ac = make_committer(dirty_files=["a.py"], commit_ok=False)
        r = ac.commit_if_dirty("some msg")
        assert not r.committed
        assert r.commit_hash is None

    def test_result_dataclass(self):
        r = AutoCommitResult(committed=True, commit_hash="abc", message="msg", files_staged=["f.py"])
        assert r.committed
        assert r.commit_hash == "abc"

    def test_exact_72_chars_not_truncated(self):
        ac = make_committer(dirty_files=["a.py"])
        desc = "a" * 72
        r = ac.commit_if_dirty(desc)
        assert r.message == desc
