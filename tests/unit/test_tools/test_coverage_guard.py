"""Tests for CoverageGuardTool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.coverage_guard import CoverageGuardTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coverage_json(files: dict) -> dict:
    """Build a minimal coverage.py JSON structure."""
    return {"files": files, "meta": {"version": "7.0"}}


def _make_file_entry(executed: list[int], missing: list[int], pct: float) -> dict:
    return {
        "executed_lines": executed,
        "missing_lines": missing,
        "excluded_lines": [],
        "missing_branches": [],
        "summary": {"percent_covered": pct},
    }


@pytest.fixture()
def tool() -> CoverageGuardTool:
    return CoverageGuardTool()


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_name(self, tool):
        assert tool.name == "coverage_guard"

    def test_has_parameters(self, tool):
        names = [p.name for p in tool.parameters]
        assert "file_path" in names
        assert "threshold" in names
        assert "test_paths" in names
        assert "use_existing" in names

    def test_ask_permission(self, tool):
        from lidco.tools.base import ToolPermission
        assert tool.permission == ToolPermission.ASK


# ---------------------------------------------------------------------------
# use_existing=True — reads from file without running pytest
# ---------------------------------------------------------------------------


class TestUseExistingTrue:
    @pytest.mark.asyncio
    async def test_returns_gaps_below_threshold(self, tool, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        data = _make_coverage_json({
            "src/foo.py": _make_file_entry([1, 2], [3, 4], 50.0),
            "src/bar.py": _make_file_entry([1, 2, 3], [], 100.0),
        })
        (lidco_dir / "coverage.json").write_text(json.dumps(data), encoding="utf-8")

        result = await tool._run(threshold=80.0, use_existing=True)

        assert result.success is False
        assert "foo.py" in result.output
        assert "bar.py" not in result.output

    @pytest.mark.asyncio
    async def test_specific_file_path(self, tool, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        data = _make_coverage_json({
            "src/foo.py": _make_file_entry([1, 2], [3, 4], 50.0),
        })
        (lidco_dir / "coverage.json").write_text(json.dumps(data), encoding="utf-8")

        result = await tool._run(file_path="src/foo.py", use_existing=True)

        assert "foo.py" in result.output

    @pytest.mark.asyncio
    async def test_specific_file_not_in_coverage_ok(self, tool, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        data = _make_coverage_json({
            "src/foo.py": _make_file_entry([1, 2, 3], [], 100.0),
        })
        (lidco_dir / "coverage.json").write_text(json.dumps(data), encoding="utf-8")

        result = await tool._run(file_path="src/other.py", use_existing=True)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_no_gaps_returns_success(self, tool, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        data = _make_coverage_json({
            "src/foo.py": _make_file_entry([1, 2, 3], [], 100.0),
        })
        (lidco_dir / "coverage.json").write_text(json.dumps(data), encoding="utf-8")

        result = await tool._run(threshold=80.0, use_existing=True)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_missing_coverage_file_error(self, tool, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        result = await tool._run(use_existing=True)

        assert result.success is False
        assert "coverage" in result.output.lower() or "not found" in result.output.lower()

    @pytest.mark.asyncio
    async def test_malformed_json_error(self, tool, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        (lidco_dir / "coverage.json").write_text("not json!", encoding="utf-8")

        result = await tool._run(use_existing=True)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_metadata_keys(self, tool, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        data = _make_coverage_json({
            "src/foo.py": _make_file_entry([1], [2], 50.0),
        })
        (lidco_dir / "coverage.json").write_text(json.dumps(data), encoding="utf-8")

        result = await tool._run(threshold=80.0, use_existing=True)

        assert "total_files" in result.metadata
        assert "gap_files" in result.metadata
        assert "threshold" in result.metadata


# ---------------------------------------------------------------------------
# use_existing=False — runs pytest subprocess
# ---------------------------------------------------------------------------


class TestRunPytest:
    @pytest.mark.asyncio
    async def test_pytest_failure_returns_error(self, tool, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch(
            "lidco.tools.coverage_guard._run_pytest_coverage",
            return_value="pytest crashed",
        ):
            result = await tool._run(use_existing=False)

        assert result.success is False
        assert "pytest crashed" in result.output

    @pytest.mark.asyncio
    async def test_pytest_success_reads_json(self, tool, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        data = _make_coverage_json({
            "src/foo.py": _make_file_entry([1, 2, 3], [], 100.0),
        })
        (lidco_dir / "coverage.json").write_text(json.dumps(data), encoding="utf-8")

        with patch(
            "lidco.tools.coverage_guard._run_pytest_coverage",
            return_value=None,
        ):
            result = await tool._run(threshold=80.0, use_existing=False)

        assert result.success is True


# ---------------------------------------------------------------------------
# _run_pytest_coverage (subprocess helper)
# ---------------------------------------------------------------------------


class TestRunPytestCoverage:
    def test_returns_none_on_success(self, tmp_path):
        from lidco.tools.coverage_guard import _run_pytest_coverage

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
            result = _run_pytest_coverage(tmp_path, ["tests/"], tmp_path / "cov.json")

        assert result is None

    def test_returns_error_on_bad_returncode(self, tmp_path):
        from lidco.tools.coverage_guard import _run_pytest_coverage

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=2, stderr="collection error", stdout=""
            )
            result = _run_pytest_coverage(tmp_path, ["tests/"], tmp_path / "cov.json")

        assert result is not None
        assert "collection error" in result

    def test_timeout_returns_error(self, tmp_path):
        import subprocess
        from lidco.tools.coverage_guard import _run_pytest_coverage

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["pytest"], 120)):
            result = _run_pytest_coverage(tmp_path, ["tests/"], tmp_path / "cov.json")

        assert result is not None
        assert "timed out" in result.lower()

    def test_file_not_found_returns_error(self, tmp_path):
        from lidco.tools.coverage_guard import _run_pytest_coverage

        with patch("subprocess.run", side_effect=FileNotFoundError("no python")):
            result = _run_pytest_coverage(tmp_path, ["tests/"], tmp_path / "cov.json")

        assert result is not None

    def test_creates_lidco_dir(self, tmp_path):
        from lidco.tools.coverage_guard import _run_pytest_coverage

        json_out = tmp_path / "new_dir" / "coverage.json"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
            _run_pytest_coverage(tmp_path, ["tests/"], json_out)

        assert json_out.parent.exists()
