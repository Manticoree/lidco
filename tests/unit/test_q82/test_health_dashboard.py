"""Tests for ProjectHealthDashboard (T535)."""
from __future__ import annotations
from pathlib import Path
import pytest
from lidco.analytics.health_dashboard import ProjectHealthDashboard, HealthReport


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_collect_basic(tmp_path):
    _write(tmp_path / "src" / "mod.py", "def foo(): pass\n" * 10)
    _write(tmp_path / "tests" / "test_mod.py", "def test_foo(): pass\n" * 5)
    dash = ProjectHealthDashboard(tmp_path)
    report = dash.collect()
    assert report.source_files == 1
    assert report.test_files == 1
    assert report.test_count == 5


def test_score_between_0_and_1(tmp_path):
    _write(tmp_path / "mod.py", "x = 1\n")
    dash = ProjectHealthDashboard(tmp_path)
    report = dash.collect()
    assert 0.0 <= report.score <= 1.0


def test_large_files_detected(tmp_path):
    big_content = "x = 1\n" * 500
    _write(tmp_path / "big.py", big_content)
    dash = ProjectHealthDashboard(tmp_path)
    report = dash.collect()
    assert len(report.large_files) == 1


def test_no_large_files(tmp_path):
    _write(tmp_path / "small.py", "x = 1\n" * 10)
    dash = ProjectHealthDashboard(tmp_path)
    report = dash.collect()
    assert len(report.large_files) == 0


def test_format_table_contains_key_info(tmp_path):
    _write(tmp_path / "mod.py", "x = 1\n")
    dash = ProjectHealthDashboard(tmp_path)
    report = dash.collect()
    table = report.format_table()
    assert "Source files" in table
    assert "Health score" in table
    assert "Test files" in table


def test_empty_project(tmp_path):
    dash = ProjectHealthDashboard(tmp_path)
    report = dash.collect()
    assert report.source_files == 0
    assert report.test_files == 0
    assert report.total_lines == 0


def test_avg_file_lines(tmp_path):
    _write(tmp_path / "a.py", "x\n" * 100)
    _write(tmp_path / "b.py", "y\n" * 200)
    dash = ProjectHealthDashboard(tmp_path)
    report = dash.collect()
    assert report.avg_file_lines == pytest.approx(150.0)


def test_health_report_details(tmp_path):
    _write(tmp_path / "mod.py", "x = 1\n")
    dash = ProjectHealthDashboard(tmp_path)
    report = dash.collect()
    assert "test_ratio" in report.details
