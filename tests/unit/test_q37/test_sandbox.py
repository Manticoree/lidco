"""Tests for SandboxValidator — Q37 task 249."""

from __future__ import annotations

from pathlib import Path

import pytest

from lidco.core.config import SandboxConfig
from lidco.core.sandbox import SandboxValidator


def _make_validator(
    project_dir: Path,
    writable_roots: list[str] | None = None,
    blocked_paths: list[str] | None = None,
) -> SandboxValidator:
    config = SandboxConfig(
        enabled=True,
        writable_roots=writable_roots or [],
        blocked_paths=blocked_paths or [".git", ".lidco"],
    )
    return SandboxValidator(config, project_dir)


class TestValidateWritePath:
    def test_project_dir_allowed(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        allowed, reason = v.validate_write_path(str(tmp_path / "src" / "foo.py"))
        assert allowed

    def test_outside_project_denied(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        allowed, reason = v.validate_write_path("/etc/passwd")
        assert not allowed
        assert "outside" in reason.lower() or "writable" in reason.lower()

    def test_dot_git_blocked(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        allowed, reason = v.validate_write_path(str(tmp_path / ".git" / "config"))
        assert not allowed
        assert ".git" in reason

    def test_dot_lidco_blocked(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        allowed, reason = v.validate_write_path(str(tmp_path / ".lidco" / "secrets.json"))
        assert not allowed

    def test_custom_writable_root(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom"
        custom.mkdir()
        v = _make_validator(tmp_path, writable_roots=["custom"])
        allowed, _ = v.validate_write_path(str(custom / "file.txt"))
        assert allowed

    def test_custom_writable_root_denies_default(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom"
        custom.mkdir()
        v = _make_validator(tmp_path, writable_roots=["custom"])
        allowed, _ = v.validate_write_path(str(tmp_path / "src" / "foo.py"))
        assert not allowed

    def test_nested_path_inside_blocked(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path, blocked_paths=["secrets"])
        allowed, _ = v.validate_write_path(str(tmp_path / "secrets" / "api.key"))
        assert not allowed


class TestValidateCommand:
    def test_clean_command_allowed(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        allowed, reason = v.validate_command("echo hello")
        assert allowed

    def test_redirect_inside_project_allowed(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        allowed, _ = v.validate_command(f"echo hello > {tmp_path}/output.txt")
        assert allowed

    def test_redirect_outside_project_denied(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        allowed, reason = v.validate_command("echo evil > /etc/crontab")
        assert not allowed

    def test_redirect_to_blocked_denied(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        allowed, reason = v.validate_command(f"echo cfg > {tmp_path}/.git/config")
        assert not allowed

    def test_tee_outside_denied(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        allowed, _ = v.validate_command("cat file.txt | tee /etc/evil")
        assert not allowed

    def test_tee_inside_allowed(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        allowed, _ = v.validate_command(f"cat file.txt | tee {tmp_path}/log.txt")
        assert allowed


class TestIsBlockedPath:
    def test_blocked(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        assert v.is_blocked_path(str(tmp_path / ".git" / "HEAD"))

    def test_not_blocked(self, tmp_path: Path) -> None:
        v = _make_validator(tmp_path)
        assert not v.is_blocked_path(str(tmp_path / "src" / "foo.py"))
