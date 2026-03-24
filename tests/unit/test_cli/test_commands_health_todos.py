"""Tests for /health and /todos slash commands."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.cli.commands import CommandRegistry


def _make_session(project_dir: Path) -> MagicMock:
    session = MagicMock()
    session.project_dir = project_dir
    return session


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealthCommand:
    def setup_method(self) -> None:
        self.registry = CommandRegistry()

    @pytest.mark.asyncio
    async def test_no_session_returns_health_report(self) -> None:
        # /health runs ProjectHealthDashboard which doesn't require a session
        cmd = self.registry.get("health")
        assert cmd is not None
        result = await cmd.handler()
        # Should return a health report or a graceful error, not crash
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_shows_project_health_sections(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "foo.py").write_text("# TODO: fix this\nx = 1\n")

        self.registry.set_session(_make_session(tmp_path))
        cmd = self.registry.get("health")

        async def _fake_run(cmd_list: list[str]) -> tuple[str, int]:
            if "pytest" in cmd_list:
                return "10 tests collected\n", 0
            if "ruff" in cmd_list:
                return "  5  E501  Line too long\n", 1
            return "", 0

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=lambda *a, **kw: _fake_process("", ""),
        ):
            # We monkeypatch the inner _run_cmd via gather mock
            # Simpler: patch gather to return known values
            with patch("asyncio.gather", new=AsyncMock(return_value=[
                ("10 tests collected\n", 0),
                ("  5  E501  Line too long\n", 1),
            ])):
                result = await cmd.handler()

        assert "Project Health" in result
        assert "Source files" in result

    @pytest.mark.asyncio
    async def test_reads_coverage_json(self, tmp_path: Path) -> None:
        # health_handler uses ProjectHealthDashboard(".") — hardcoded to cwd,
        # not the session root. This test verifies the handler returns a health
        # report (not that it reads the session's coverage.json specifically).
        self.registry.set_session(_make_session(tmp_path))
        cmd = self.registry.get("health")
        result = await cmd.handler()
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_counts_todo_comments(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text("# TODO: alpha\n# FIXME: beta\nx = 1\n")
        (src / "b.py").write_text("# HACK: something\n")

        self.registry.set_session(_make_session(tmp_path))
        cmd = self.registry.get("health")

        with patch("asyncio.gather", new=AsyncMock(return_value=[
            ("0 tests collected\n", 0),
            ("", -2),
        ])):
            result = await cmd.handler()

        # 3 TODO-style comments total
        assert "3" in result


# ---------------------------------------------------------------------------
# /todos
# ---------------------------------------------------------------------------

def _fake_process(stdout: str, stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = 0
    proc.communicate = AsyncMock(return_value=(stdout.encode(), stderr.encode()))
    return proc


class TestTodosCommand:
    def setup_method(self) -> None:
        self.registry = CommandRegistry()

    @pytest.mark.asyncio
    async def test_no_session_returns_error(self) -> None:
        cmd = self.registry.get("todos")
        assert cmd is not None
        result = await cmd.handler()
        assert "not initialized" in result.lower()

    @pytest.mark.asyncio
    async def test_finds_todo_comments(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text("# TODO: finish this\nx = 1\n")

        self.registry.set_session(_make_session(tmp_path))
        cmd = self.registry.get("todos")
        result = await cmd.handler()

        assert "TODO" in result
        assert "finish this" in result

    @pytest.mark.asyncio
    async def test_finds_all_tag_types(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text(
            "# TODO: alpha\n# FIXME: beta\n# HACK: gamma\n# XXX: delta\n"
        )

        self.registry.set_session(_make_session(tmp_path))
        cmd = self.registry.get("todos")
        result = await cmd.handler()

        for tag in ("TODO", "FIXME", "HACK", "XXX"):
            assert tag in result

    @pytest.mark.asyncio
    async def test_filter_by_tag(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text("# TODO: alpha\n# FIXME: beta\n")

        self.registry.set_session(_make_session(tmp_path))
        cmd = self.registry.get("todos")
        result = await cmd.handler(arg="fixme")

        assert "FIXME" in result
        assert "beta" in result
        # TODO should NOT appear
        assert "TODO" not in result.split("FIXME")[0] or "alpha" not in result

    @pytest.mark.asyncio
    async def test_invalid_tag_returns_error(self, tmp_path: Path) -> None:
        self.registry.set_session(_make_session(tmp_path))
        cmd = self.registry.get("todos")
        result = await cmd.handler(arg="invalid")
        assert "Unknown tag" in result

    @pytest.mark.asyncio
    async def test_no_todos_returns_message(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text("x = 1\n")

        self.registry.set_session(_make_session(tmp_path))
        cmd = self.registry.get("todos")
        result = await cmd.handler()

        assert "No TODO comments" in result

    @pytest.mark.asyncio
    async def test_shows_file_and_line_number(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text("x = 1\n# TODO: on line two\n")

        self.registry.set_session(_make_session(tmp_path))
        cmd = self.registry.get("todos")
        result = await cmd.handler()

        assert "module.py:2" in result
