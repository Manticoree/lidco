"""Tests for /index and /index-status slash commands."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.cli.commands import CommandRegistry
from lidco.index.db import IndexDatabase
from lidco.index.schema import FileRecord


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_session(tmp_path: Path) -> MagicMock:
    """Create a minimal fake Session."""
    session = MagicMock()
    session.project_dir = tmp_path
    session.index_enricher = None
    return session


def _make_project(tmp_path: Path) -> None:
    """Write a tiny fake Python project."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    (src / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text("def test_ok(): pass\n", encoding="utf-8")


@pytest.fixture()
def registry(tmp_path: Path) -> CommandRegistry:
    reg = CommandRegistry()
    reg.set_session(_make_session(tmp_path))
    return reg


@pytest.fixture()
def project_registry(tmp_path: Path) -> CommandRegistry:
    _make_project(tmp_path)
    reg = CommandRegistry()
    reg.set_session(_make_session(tmp_path))
    return reg


# ── /index ────────────────────────────────────────────────────────────────────


class TestIndexCommand:
    def test_command_registered(self, registry: CommandRegistry) -> None:
        assert registry.get("index") is not None

    def test_no_session_returns_error(self) -> None:
        reg = CommandRegistry()
        reg._session = None
        import asyncio
        result = asyncio.run(reg.get("index").handler(arg=""))
        assert "Session not initialized" in result

    def test_invalid_arg_returns_usage(self, registry: CommandRegistry) -> None:
        import asyncio
        result = asyncio.run(registry.get("index").handler(arg="bogus"))
        assert "Usage" in result

    def test_full_index_adds_files(self, project_registry: CommandRegistry) -> None:
        import asyncio
        result = asyncio.run(project_registry.get("index").handler(arg="full"))
        assert "Added: 3" in result
        assert "files" in result

    def test_incremental_arg_works(self, project_registry: CommandRegistry) -> None:
        import asyncio
        # First run full
        asyncio.run(project_registry.get("index").handler(arg="full"))
        # Then incremental should skip all (nothing changed)
        result = asyncio.run(project_registry.get("index").handler(arg="incremental"))
        assert "Skipped: 3" in result

    def test_default_arg_runs_full_on_empty(self, project_registry: CommandRegistry) -> None:
        import asyncio
        result = asyncio.run(project_registry.get("index").handler(arg=""))
        assert "Added: 3" in result

    def test_result_shows_symbol_count(self, project_registry: CommandRegistry) -> None:
        import asyncio
        result = asyncio.run(project_registry.get("index").handler(arg="full"))
        assert "symbols" in result

    def test_enricher_updated_after_index(self, project_registry: CommandRegistry) -> None:
        import asyncio
        asyncio.run(project_registry.get("index").handler(arg="full"))
        session = project_registry._session
        assert session.index_enricher is not None
        assert session.index_enricher.is_indexed()

    def test_session_message_at_end(self, project_registry: CommandRegistry) -> None:
        import asyncio
        result = asyncio.run(project_registry.get("index").handler(arg="full"))
        assert "Structural context" in result

    def test_languages_shown(self, project_registry: CommandRegistry) -> None:
        import asyncio
        result = asyncio.run(project_registry.get("index").handler(arg="full"))
        assert "python" in result


# ── /index-status ─────────────────────────────────────────────────────────────


class TestIndexStatusCommand:
    def test_command_registered(self, registry: CommandRegistry) -> None:
        assert registry.get("index-status") is not None

    def test_no_session_returns_error(self) -> None:
        reg = CommandRegistry()
        reg._session = None
        import asyncio
        result = asyncio.run(reg.get("index-status").handler())
        assert "Session not initialized" in result

    def test_no_db_prompts_to_run_index(self, registry: CommandRegistry) -> None:
        import asyncio
        result = asyncio.run(registry.get("index-status").handler())
        assert "No index found" in result
        assert "/index" in result

    def test_after_index_shows_stats(self, project_registry: CommandRegistry) -> None:
        import asyncio
        asyncio.run(project_registry.get("index").handler(arg="full"))
        result = asyncio.run(project_registry.get("index-status").handler())
        assert "Files:" in result
        assert "3" in result

    def test_shows_last_indexed_timestamp(self, project_registry: CommandRegistry) -> None:
        import asyncio
        asyncio.run(project_registry.get("index").handler(arg="full"))
        result = asyncio.run(project_registry.get("index-status").handler())
        assert "Last indexed:" in result

    def test_shows_symbol_count(self, project_registry: CommandRegistry) -> None:
        import asyncio
        asyncio.run(project_registry.get("index").handler(arg="full"))
        result = asyncio.run(project_registry.get("index-status").handler())
        assert "Symbols:" in result

    def test_shows_language_breakdown(self, project_registry: CommandRegistry) -> None:
        import asyncio
        asyncio.run(project_registry.get("index").handler(arg="full"))
        result = asyncio.run(project_registry.get("index-status").handler())
        assert "python" in result.lower()

    def test_fresh_index_is_up_to_date(self, project_registry: CommandRegistry) -> None:
        import asyncio
        asyncio.run(project_registry.get("index").handler(arg="full"))
        result = asyncio.run(project_registry.get("index-status").handler())
        assert "up to date" in result

    def test_stale_index_warns(self, project_registry: CommandRegistry, tmp_path: Path) -> None:
        import asyncio
        # Build index, then manually set a very old timestamp
        asyncio.run(project_registry.get("index").handler(arg="full"))
        db = IndexDatabase(tmp_path / ".lidco" / "project_index.db")
        db.set_meta("last_indexed_at", str(time.time() - 25 * 3600))
        db.close()
        result = asyncio.run(project_registry.get("index-status").handler())
        assert "older than 24 hours" in result


# ── lidco index subcommand ────────────────────────────────────────────────────


class TestIndexSubcommand:
    def test_full_index_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        _make_project(tmp_path)
        from lidco.__main__ import _run_index
        _run_index(["--dir", str(tmp_path)])
        captured = capsys.readouterr()
        assert "Done:" in captured.out
        assert "files" in captured.out

    def test_incremental_flag(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        _make_project(tmp_path)
        from lidco.__main__ import _run_index
        # First full
        _run_index(["--dir", str(tmp_path)])
        capsys.readouterr()
        # Then incremental — nothing changed, should skip all
        _run_index(["--dir", str(tmp_path), "--incremental"])
        captured = capsys.readouterr()
        assert "Done:" in captured.out

    def test_codemap_flag_writes_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        _make_project(tmp_path)
        from lidco.__main__ import _run_index
        _run_index(["--dir", str(tmp_path), "--codemap"])
        codemap = tmp_path / "CODEMAPS.md"
        assert codemap.exists()
        assert "# Project Codemap" in codemap.read_text(encoding="utf-8")

    def test_unknown_arg_exits(self, tmp_path: Path) -> None:
        from lidco.__main__ import _run_index
        with pytest.raises(SystemExit):
            _run_index(["--unknown-flag"])

    def test_creates_db_in_lidco_dir(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        _make_project(tmp_path)
        from lidco.__main__ import _run_index
        _run_index(["--dir", str(tmp_path)])
        assert (tmp_path / ".lidco" / "project_index.db").exists()
