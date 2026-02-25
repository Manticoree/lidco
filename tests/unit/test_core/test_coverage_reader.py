"""Tests for coverage_reader — test coverage context for agents."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lidco.core.coverage_reader import (
    _parse_coverage_json,
    build_coverage_context,
    read_coverage,
)


def _write_coverage_json(path: Path, files: dict[str, float]) -> None:
    """Write a minimal coverage.py JSON report to *path*."""
    project_dir = path.parent.parent  # .lidco/coverage.json → project root
    data = {
        "files": {
            str(project_dir / rel): {
                "summary": {"percent_covered": pct}
            }
            for rel, pct in files.items()
        },
        "totals": {"percent_covered": sum(files.values()) / len(files) if files else 0},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class TestParseCoverageJson:
    def test_parses_file_percentages(self, tmp_path):
        json_path = tmp_path / ".lidco" / "coverage.json"
        _write_coverage_json(json_path, {"src/foo.py": 85.5, "src/bar.py": 40.0})

        result = _parse_coverage_json(json_path)
        assert "src/foo.py" in result
        assert result["src/foo.py"] == 85.5
        assert result["src/bar.py"] == 40.0

    def test_missing_file_returns_empty(self, tmp_path):
        result = _parse_coverage_json(tmp_path / "nonexistent.json")
        assert result == {}

    def test_invalid_json_returns_empty(self, tmp_path):
        bad_json = tmp_path / ".lidco" / "coverage.json"
        bad_json.parent.mkdir(parents=True)
        bad_json.write_text("not json", encoding="utf-8")
        result = _parse_coverage_json(bad_json)
        assert result == {}

    def test_missing_percent_covered_skipped(self, tmp_path):
        json_path = tmp_path / ".lidco" / "coverage.json"
        json_path.parent.mkdir(parents=True)
        json_path.write_text(
            json.dumps({"files": {"src/foo.py": {"summary": {}}}}),
            encoding="utf-8",
        )
        result = _parse_coverage_json(json_path)
        assert result == {}


class TestReadCoverage:
    def test_reads_existing_json(self, tmp_path):
        json_path = tmp_path / ".lidco" / "coverage.json"
        _write_coverage_json(json_path, {"src/mod.py": 72.3})
        result = read_coverage(tmp_path)
        assert "src/mod.py" in result

    def test_returns_empty_when_no_data(self, tmp_path):
        result = read_coverage(tmp_path)
        assert result == {}


class TestBuildCoverageContext:
    def test_returns_empty_when_no_coverage(self, tmp_path):
        result = build_coverage_context(tmp_path)
        assert result == ""

    def test_section_header_present(self, tmp_path):
        json_path = tmp_path / ".lidco" / "coverage.json"
        _write_coverage_json(json_path, {"src/a.py": 80.0})
        result = build_coverage_context(tmp_path)
        assert "## Test Coverage" in result

    def test_low_coverage_flagged(self, tmp_path):
        json_path = tmp_path / ".lidco" / "coverage.json"
        _write_coverage_json(json_path, {"src/low.py": 25.0, "src/high.py": 95.0})
        result = build_coverage_context(tmp_path, low_threshold=60.0)
        assert "⚠" in result  # warning marker for low coverage
        lines_with_warning = [l for l in result.splitlines() if "⚠" in l]
        assert any("low.py" in l for l in lines_with_warning)

    def test_sorted_ascending_by_coverage(self, tmp_path):
        json_path = tmp_path / ".lidco" / "coverage.json"
        _write_coverage_json(json_path, {
            "src/a.py": 90.0,
            "src/b.py": 30.0,
            "src/c.py": 60.0,
        })
        result = build_coverage_context(tmp_path)
        # b (30%) should appear before a (90%)
        assert result.index("src/b.py") < result.index("src/a.py")

    def test_respects_limit(self, tmp_path):
        files = {f"src/f{i}.py": float(i * 5) for i in range(20)}
        json_path = tmp_path / ".lidco" / "coverage.json"
        _write_coverage_json(json_path, files)
        result = build_coverage_context(tmp_path, limit=5)
        # Should mention omitted files
        assert "more files" in result

    def test_percentage_displayed(self, tmp_path):
        json_path = tmp_path / ".lidco" / "coverage.json"
        _write_coverage_json(json_path, {"src/mod.py": 73.4})
        result = build_coverage_context(tmp_path)
        assert "73.4" in result
