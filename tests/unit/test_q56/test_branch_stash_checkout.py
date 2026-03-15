"""Tests for Task 377 — /branch, /checkout, /stash commands."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest


def _make_registry():
    from lidco.cli.commands import CommandRegistry
    registry = CommandRegistry()
    registry.set_session(MagicMock())
    return registry


def _invoke(handler, arg: str = "") -> str:
    return asyncio.run(handler(arg=arg))


def _mock_git(returncode=0, stdout="", stderr=""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


class TestBranchCommand:
    def test_branch_registered(self):
        reg = _make_registry()
        assert reg.get("branch") is not None

    def test_branch_list(self):
        reg = _make_registry()
        cmd = reg.get("branch")
        with patch("subprocess.run", return_value=_mock_git(0, "* main\n  feature/foo\n")):
            result = _invoke(cmd.handler, "list")
        assert "main" in result
        assert "feature/foo" in result

    def test_branch_list_default_no_arg(self):
        reg = _make_registry()
        cmd = reg.get("branch")
        with patch("subprocess.run", return_value=_mock_git(0, "* main\n")):
            result = _invoke(cmd.handler, "")
        assert "main" in result

    def test_branch_create(self):
        reg = _make_registry()
        cmd = reg.get("branch")
        with patch("subprocess.run", return_value=_mock_git(0, "")):
            result = _invoke(cmd.handler, "create my-feature")
        assert "my-feature" in result
        assert "created" in result.lower()

    def test_branch_delete(self):
        reg = _make_registry()
        cmd = reg.get("branch")
        with patch("subprocess.run", return_value=_mock_git(0, "")):
            result = _invoke(cmd.handler, "delete old-branch")
        assert "old-branch" in result
        assert "deleted" in result.lower()

    def test_branch_rename(self):
        reg = _make_registry()
        cmd = reg.get("branch")
        with patch("subprocess.run", return_value=_mock_git(0, "")):
            result = _invoke(cmd.handler, "rename old-name new-name")
        assert "old-name" in result
        assert "new-name" in result

    def test_branch_git_not_found(self):
        reg = _make_registry()
        cmd = reg.get("branch")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _invoke(cmd.handler, "list")
        assert "error" in result.lower() or "not found" in result.lower()

    def test_branch_unknown_subcommand_shows_help(self):
        reg = _make_registry()
        cmd = reg.get("branch")
        result = _invoke(cmd.handler, "unknown-sub")
        assert "Usage" in result or "branch" in result.lower()


class TestCheckoutCommand:
    def test_checkout_registered(self):
        reg = _make_registry()
        assert reg.get("checkout") is not None

    def test_checkout_no_arg_shows_usage(self):
        reg = _make_registry()
        cmd = reg.get("checkout")
        result = _invoke(cmd.handler, "")
        assert "Usage" in result

    def test_checkout_success(self):
        reg = _make_registry()
        cmd = reg.get("checkout")
        with patch("subprocess.run", return_value=_mock_git(0, "", "Switched to branch 'main'")):
            result = _invoke(cmd.handler, "main")
        assert "main" in result

    def test_checkout_failure(self):
        reg = _make_registry()
        cmd = reg.get("checkout")
        with patch("subprocess.run", return_value=_mock_git(1, "", "error: pathspec 'nonexistent'")):
            result = _invoke(cmd.handler, "nonexistent")
        assert "failed" in result.lower() or "error" in result.lower()

    def test_checkout_git_not_found(self):
        reg = _make_registry()
        cmd = reg.get("checkout")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _invoke(cmd.handler, "main")
        assert "not found" in result.lower()


class TestStashCommand:
    def test_stash_registered(self):
        reg = _make_registry()
        assert reg.get("stash") is not None

    def test_stash_list(self):
        reg = _make_registry()
        cmd = reg.get("stash")
        with patch("subprocess.run", return_value=_mock_git(0, "stash@{0}: WIP on main")):
            result = _invoke(cmd.handler, "list")
        assert "stash@{0}" in result

    def test_stash_list_empty(self):
        reg = _make_registry()
        cmd = reg.get("stash")
        with patch("subprocess.run", return_value=_mock_git(0, "")):
            result = _invoke(cmd.handler, "list")
        assert "no stash" in result.lower() or "not found" in result.lower()

    def test_stash_push(self):
        reg = _make_registry()
        cmd = reg.get("stash")
        with patch("subprocess.run", return_value=_mock_git(0, "Saved working directory")):
            result = _invoke(cmd.handler, "push my work")
        assert "stash" in result.lower() or "saved" in result.lower()

    def test_stash_pop(self):
        reg = _make_registry()
        cmd = reg.get("stash")
        with patch("subprocess.run", return_value=_mock_git(0, "Applied")):
            result = _invoke(cmd.handler, "pop")
        assert "pop" in result.lower() or "applied" in result.lower() or "stash" in result.lower()

    def test_stash_drop(self):
        reg = _make_registry()
        cmd = reg.get("stash")
        with patch("subprocess.run", return_value=_mock_git(0, "Dropped")):
            result = _invoke(cmd.handler, "drop 0")
        assert "drop" in result.lower() or "dropped" in result.lower()

    def test_stash_git_not_found(self):
        reg = _make_registry()
        cmd = reg.get("stash")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _invoke(cmd.handler, "list")
        assert "not found" in result.lower() or "error" in result.lower()

    def test_stash_unknown_subcommand_shows_help(self):
        reg = _make_registry()
        cmd = reg.get("stash")
        result = _invoke(cmd.handler, "unknown")
        assert "Usage" in result or "stash" in result.lower()
