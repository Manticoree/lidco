"""Tests for RegressionDetector — Task 411."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.proactive.regression_detector import RegressionDetector, RegressionResult


class TestRegressionResult:

    def test_fields(self) -> None:
        r = RegressionResult(passed=5, failed=1, test_files_run=["test_a.py"], duration_ms=123.4)
        assert r.passed == 5
        assert r.failed == 1
        assert r.test_files_run == ["test_a.py"]
        assert r.duration_ms == 123.4

    def test_frozen(self) -> None:
        r = RegressionResult(passed=0, failed=0, test_files_run=[], duration_ms=0.0)
        with pytest.raises((AttributeError, TypeError)):
            r.passed = 1  # type: ignore[misc]


class TestRegressionDetectorFindTests:

    def test_find_tests_empty_stem(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        results = detector.find_related_tests(str(tmp_path / "a.py"))
        assert results == []

    def test_find_tests_no_tests_dir(self, tmp_path: Path) -> None:
        src_file = tmp_path / "auth.py"
        src_file.write_text("# auth module")
        detector = RegressionDetector(str(tmp_path))
        results = detector.find_related_tests(str(src_file))
        assert results == []

    def test_find_tests_by_filename(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_auth.py"
        test_file.write_text("def test_login(): pass")
        src_file = tmp_path / "auth.py"
        src_file.write_text("# auth")
        detector = RegressionDetector(str(tmp_path))
        results = detector.find_related_tests(str(src_file))
        assert str(test_file) in results

    def test_find_tests_by_content(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_misc.py"
        test_file.write_text("from mymodule import myfunction\ndef test_myfunction(): pass")
        src_file = tmp_path / "myfunction.py"
        src_file.write_text("def myfunction(): pass")
        detector = RegressionDetector(str(tmp_path))
        results = detector.find_related_tests(str(src_file))
        assert str(test_file) in results


class TestRegressionDetectorParseOutput:

    def test_parse_passed_only(self) -> None:
        out = "3 passed in 0.12s"
        passed, failed = RegressionDetector._parse_pytest_output(out)
        assert passed == 3
        assert failed == 0

    def test_parse_failed_only(self) -> None:
        out = "2 failed in 0.5s"
        passed, failed = RegressionDetector._parse_pytest_output(out)
        assert passed == 0
        assert failed == 2

    def test_parse_mixed(self) -> None:
        out = "5 passed, 1 failed in 1.2s"
        passed, failed = RegressionDetector._parse_pytest_output(out)
        assert passed == 5
        assert failed == 1

    def test_parse_empty(self) -> None:
        passed, failed = RegressionDetector._parse_pytest_output("")
        assert passed == 0
        assert failed == 0


class TestRegressionDetectorDetect:

    def test_detect_no_tests(self, tmp_path: Path) -> None:
        src = tmp_path / "foo.py"
        src.write_text("x = 1")
        detector = RegressionDetector(str(tmp_path))

        async def run() -> RegressionResult:
            return await detector.detect(str(src))

        result = asyncio.run(run())
        assert result.test_files_run == []
        assert result.passed == 0
        assert result.failed == 0

    def test_detect_with_mock_pytest(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_parser.py"
        test_file.write_text("def test_ok(): pass")
        src = tmp_path / "parser.py"
        src.write_text("def parse(): pass")
        detector = RegressionDetector(str(tmp_path))

        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"1 passed in 0.1s", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
            async def run() -> RegressionResult:
                return await detector.detect(str(src))

            result = asyncio.run(run())
            assert result.passed == 1
            assert result.failed == 0
            assert len(result.test_files_run) == 1
