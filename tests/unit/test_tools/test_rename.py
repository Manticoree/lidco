"""Tests for RenameSymbolTool."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from lidco.tools.rename import RenameSymbolTool


class TestRenameSymbolTool:
    def setup_method(self) -> None:
        self.tool = RenameSymbolTool()

    # --- metadata ---
    def test_name(self) -> None:
        assert self.tool.name == "rename_symbol"

    def test_has_five_parameters(self) -> None:
        names = {p.name for p in self.tool.parameters}
        assert names == {"old_name", "new_name", "glob_pattern", "whole_word", "dry_run"}

    # --- validation ---
    @pytest.mark.asyncio
    async def test_missing_old_name_returns_error(self) -> None:
        result = await self.tool._run(old_name="", new_name="Bar")
        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_missing_new_name_returns_error(self) -> None:
        result = await self.tool._run(old_name="Foo", new_name="")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_same_name_is_noop(self) -> None:
        result = await self.tool._run(old_name="Foo", new_name="Foo")
        assert result.success is True
        assert "nothing to do" in result.output.lower()

    # --- dry_run ---
    @pytest.mark.asyncio
    async def test_dry_run_does_not_modify_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "a.py"
        f.write_text("class OldName:\n    pass\n")

        result = await self.tool._run(
            old_name="OldName", new_name="NewName", dry_run=True
        )
        assert result.success is True
        assert "Dry run" in result.output
        # File must be unchanged
        assert f.read_text() == "class OldName:\n    pass\n"

    @pytest.mark.asyncio
    async def test_dry_run_reports_what_would_change(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("OldName()\nOldName()\n")

        result = await self.tool._run(
            old_name="OldName", new_name="NewName", dry_run=True
        )
        assert result.metadata["total_replacements"] == 2
        assert result.metadata["total_files"] == 1
        assert result.metadata["dry_run"] is True

    # --- actual rename ---
    @pytest.mark.asyncio
    async def test_renames_across_multiple_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("from foo import OldName\n")
        (tmp_path / "b.py").write_text("class OldName:\n    pass\n")
        (tmp_path / "c.py").write_text("# no match here\n")

        result = await self.tool._run(old_name="OldName", new_name="NewName")
        assert result.success is True
        assert "a.py" in (tmp_path / "a.py").read_text() is False or "NewName" in (tmp_path / "a.py").read_text()
        assert "NewName" in (tmp_path / "b.py").read_text()
        assert result.metadata["total_files"] == 2

    # --- whole_word ---
    @pytest.mark.asyncio
    async def test_whole_word_true_skips_substrings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("OldName\nOldNameExtended\n")

        result = await self.tool._run(
            old_name="OldName", new_name="NewName", whole_word=True
        )
        content = (tmp_path / "a.py").read_text()
        assert "NewName\n" in content
        assert "OldNameExtended" in content  # not renamed

    @pytest.mark.asyncio
    async def test_whole_word_false_replaces_substrings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("OldName\nOldNameExtended\n")

        result = await self.tool._run(
            old_name="OldName", new_name="NewName", whole_word=False
        )
        content = (tmp_path / "a.py").read_text()
        assert "OldName" not in content
        assert "NewNameExtended" in content

    # --- no match ---
    @pytest.mark.asyncio
    async def test_no_match_returns_friendly_message(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("x = 1\n")

        result = await self.tool._run(old_name="OldName", new_name="NewName")
        assert result.success is True
        assert "No occurrences" in result.output
        assert result.metadata["total_files"] == 0

    # --- metadata ---
    @pytest.mark.asyncio
    async def test_changed_files_in_metadata(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "x.py").write_text("OldName\n")

        result = await self.tool._run(old_name="OldName", new_name="NewName")
        assert "x.py" in result.metadata["changed_files"]
