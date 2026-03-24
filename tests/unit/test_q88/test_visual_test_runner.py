"""Tests for VisualTestRunner (T575)."""
from __future__ import annotations
from pathlib import Path
import pytest
from lidco.browser.visual_test_runner import VisualTestRunner, VisualTestCase, VisualTestResult


DUMMY_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
DUMMY_PNG_2 = b"\x89PNG\r\n\x1a\n" + b"\x01" * 50


def test_first_run_creates_baseline(tmp_path):
    runner = VisualTestRunner(baseline_dir=tmp_path / "baselines")
    test = VisualTestCase(name="home", url="http://example.com")
    result = runner.run_test(test, DUMMY_PNG)
    assert result.passed is True
    assert result.is_new_baseline is True
    assert (tmp_path / "baselines" / "home.png").exists()


def test_second_run_matches_baseline(tmp_path):
    runner = VisualTestRunner(baseline_dir=tmp_path / "baselines")
    test = VisualTestCase(name="home", url="")
    runner.run_test(test, DUMMY_PNG)  # create baseline
    result = runner.run_test(test, DUMMY_PNG)  # same data
    assert result.passed is True
    assert result.is_new_baseline is False


def test_changed_screenshot_fails(tmp_path):
    runner = VisualTestRunner(baseline_dir=tmp_path / "baselines")
    test = VisualTestCase(name="page", url="")
    runner.run_test(test, DUMMY_PNG)
    result = runner.run_test(test, DUMMY_PNG_2)
    assert result.passed is False


def test_update_baseline(tmp_path):
    runner = VisualTestRunner(baseline_dir=tmp_path / "baselines")
    test = VisualTestCase(name="pg", url="")
    runner.run_test(test, DUMMY_PNG)
    runner.update_baseline("pg", DUMMY_PNG_2)
    result = runner.run_test(test, DUMMY_PNG_2)
    assert result.passed is True


def test_list_baselines_empty(tmp_path):
    runner = VisualTestRunner(baseline_dir=tmp_path / "baselines")
    assert runner.list_baselines() == []


def test_list_baselines_after_create(tmp_path):
    runner = VisualTestRunner(baseline_dir=tmp_path / "baselines")
    runner.run_test(VisualTestCase(name="a", url=""), DUMMY_PNG)
    runner.run_test(VisualTestCase(name="b", url=""), DUMMY_PNG)
    assert set(runner.list_baselines()) == {"a", "b"}


def test_suite_result(tmp_path):
    runner = VisualTestRunner(baseline_dir=tmp_path / "baselines")
    tests = [
        (VisualTestCase(name="t1", url=""), DUMMY_PNG),
        (VisualTestCase(name="t2", url=""), DUMMY_PNG),
    ]
    suite = runner.run_suite(tests)
    assert suite.passed == 2
    assert suite.new_baselines == 2
    assert "passed" in suite.format_report()
