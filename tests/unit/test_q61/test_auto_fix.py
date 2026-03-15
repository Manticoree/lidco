"""Tests for AutoFixer — Task 412."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import shutil

import pytest

from lidco.proactive.auto_fix import AutoFixer, FixResult


class TestFixResult:

    def test_fields(self) -> None:
        r = FixResult(file="f.py", tool="ruff", changes_made=True, lines_changed=3, diff="")
        assert r.file == "f.py"
        assert r.tool == "ruff"
        assert r.changes_made is True
        assert r.lines_changed == 3

    def test_frozen(self) -> None:
        r = FixResult(file="f.py", tool="ruff", changes_made=False, lines_changed=0)
        with pytest.raises((AttributeError, TypeError)):
            r.tool = "isort"  # type: ignore[misc]

    def test_default_diff(self) -> None:
        r = FixResult(file="f.py", tool="ruff", changes_made=False, lines_changed=0)
        assert r.diff == ""


class TestAutoFixerReadHelper:

    def test_read_missing_file(self) -> None:
        result = AutoFixer._read("/nonexistent/path.py")
        assert result == ""

    def test_read_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        result = AutoFixer._read(str(f))
        assert result == "x = 1\n"


class TestAutoFixerMakeDiff:

    def test_diff_no_change(self) -> None:
        diff = AutoFixer._make_diff("x = 1\n", "x = 1\n", "f.py")
        assert diff == ""

    def test_diff_with_change(self) -> None:
        diff = AutoFixer._make_diff("x = 1\n", "x = 2\n", "f.py")
        assert "-x = 1" in diff
        assert "+x = 2" in diff


class TestAutoFixerFixLint:

    def test_no_ruff_returns_no_changes(self) -> None:
        fixer = AutoFixer()
        with patch("shutil.which", return_value=None):
            async def run() -> FixResult:
                return await fixer.fix_lint("any.py")
            result = asyncio.run(run())
        assert result.changes_made is False
        assert result.tool == "ruff"

    def test_ruff_preview_mode(self, tmp_path: Path) -> None:
        f = tmp_path / "code.py"
        f.write_text("import os\nimport sys\nx=1\n")
        fixer = AutoFixer()

        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"--- a\n+++ b\n-x=1\n+x = 1\n", b""))
        mock_proc.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/ruff"):
            with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
                async def run() -> FixResult:
                    return await fixer.fix_lint(str(f), preview=True)
                result = asyncio.run(run())

        assert result.tool == "ruff"
        assert result.changes_made is True

    def test_fix_lint_no_changes(self, tmp_path: Path) -> None:
        f = tmp_path / "clean.py"
        original = "x = 1\n"
        f.write_text(original)
        fixer = AutoFixer()

        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/ruff"):
            with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
                async def run() -> FixResult:
                    return await fixer.fix_lint(str(f))
                result = asyncio.run(run())

        assert result.changes_made is False


class TestAutoFixerFixImports:

    def test_no_isort_returns_no_changes(self) -> None:
        fixer = AutoFixer()
        with patch("shutil.which", return_value=None):
            async def run() -> FixResult:
                return await fixer.fix_imports("any.py")
            result = asyncio.run(run())
        assert result.changes_made is False
        assert result.tool == "isort"

    def test_isort_preview(self, tmp_path: Path) -> None:
        f = tmp_path / "code.py"
        f.write_text("import sys\nimport os\n")
        fixer = AutoFixer()

        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"-import sys\n+import os\n", b""))
        mock_proc.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/isort"):
            with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
                async def run() -> FixResult:
                    return await fixer.fix_imports(str(f), preview=True)
                result = asyncio.run(run())

        assert result.tool == "isort"


class TestAutoFixerFixTypes:

    def test_no_mypy_returns_no_changes(self) -> None:
        fixer = AutoFixer()
        with patch("shutil.which", return_value=None):
            async def run() -> FixResult:
                return await fixer.fix_types("any.py")
            result = asyncio.run(run())
        assert result.changes_made is False
        assert result.tool == "mypy"
