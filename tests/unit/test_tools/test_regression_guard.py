"""Tests for RegressionGuardTool and _parse_test_results helper."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.regression_guard import RegressionGuardTool, _parse_test_results


# ---------------------------------------------------------------------------
# _parse_test_results
# ---------------------------------------------------------------------------

class TestParseTestResults:
    def test_extracts_passed_tests(self) -> None:
        output = (
            "PASSED tests/unit/test_foo.py::test_alpha\n"
            "PASSED tests/unit/test_bar.py::test_beta\n"
        )
        result = _parse_test_results(output)
        assert result["tests/unit/test_foo.py::test_alpha"] == "pass"
        assert result["tests/unit/test_bar.py::test_beta"] == "pass"

    def test_extracts_failed_tests(self) -> None:
        output = (
            "FAILED tests/unit/test_foo.py::test_alpha - AssertionError: boom\n"
            "FAILED tests/unit/test_bar.py::test_beta\n"
        )
        result = _parse_test_results(output)
        assert result["tests/unit/test_foo.py::test_alpha"] == "fail"
        assert result["tests/unit/test_bar.py::test_beta"] == "fail"


# ---------------------------------------------------------------------------
# RegressionGuardTool._run via mocked subprocess
# ---------------------------------------------------------------------------

PYTEST_OUTPUT_NO_REGRESSION = (
    "PASSED tests/unit/test_foo.py::test_alpha\n"
    "PASSED tests/unit/test_bar.py::test_beta\n"
    "2 passed in 0.5s\n"
)

PYTEST_OUTPUT_WITH_REGRESSION = (
    "PASSED tests/unit/test_foo.py::test_alpha\n"
    "FAILED tests/unit/test_bar.py::test_beta - AssertionError: broken\n"
    "1 passed, 1 failed in 0.7s\n"
)


def _make_mock_process(stdout: str, returncode: int = 0) -> MagicMock:
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(
        return_value=(stdout.encode(), b"")
    )
    return process


@pytest.mark.asyncio
class TestRegressionGuardTool:
    async def test_no_regressions_success_true(self) -> None:
        tool = RegressionGuardTool()
        before = {
            "tests/unit/test_foo.py::test_alpha": "pass",
            "tests/unit/test_bar.py::test_beta": "fail",
        }
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process(PYTEST_OUTPUT_NO_REGRESSION),
        ):
            result = await tool.execute(before_snapshot=before)
        assert result.success is True
        assert "No regressions detected" in result.output

    async def test_regression_detected_success_false(self) -> None:
        tool = RegressionGuardTool()
        # test_beta was passing before, now it fails → regression
        before = {
            "tests/unit/test_foo.py::test_alpha": "pass",
            "tests/unit/test_bar.py::test_beta": "pass",
        }
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process(PYTEST_OUTPUT_WITH_REGRESSION, returncode=1),
        ):
            result = await tool.execute(before_snapshot=before)
        assert result.success is False

    async def test_regression_in_output_shows_warning(self) -> None:
        tool = RegressionGuardTool()
        before = {
            "tests/unit/test_bar.py::test_beta": "pass",
        }
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process(PYTEST_OUTPUT_WITH_REGRESSION, returncode=1),
        ):
            result = await tool.execute(before_snapshot=before)
        assert "REGRESSIONS DETECTED" in result.output

    async def test_fixed_tests_counted_correctly(self) -> None:
        tool = RegressionGuardTool()
        # test_alpha was failing before and now passes → fixed
        before = {
            "tests/unit/test_foo.py::test_alpha": "fail",
        }
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process(PYTEST_OUTPUT_NO_REGRESSION),
        ):
            result = await tool.execute(before_snapshot=before)
        assert result.metadata["fixed"] == ["tests/unit/test_foo.py::test_alpha"]
        assert "Fixed: 1" in result.output

    async def test_net_gain_positive(self) -> None:
        tool = RegressionGuardTool()
        # Both were failing, both now pass → net_gain = 2
        before = {
            "tests/unit/test_foo.py::test_alpha": "fail",
            "tests/unit/test_bar.py::test_beta": "fail",
        }
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process(PYTEST_OUTPUT_NO_REGRESSION),
        ):
            result = await tool.execute(before_snapshot=before)
        assert result.metadata["net_gain"] == 2
        assert "+2" in result.output

    async def test_net_gain_negative(self) -> None:
        tool = RegressionGuardTool()
        # test_beta was passing, now fails → net_gain = -1
        before = {
            "tests/unit/test_bar.py::test_beta": "pass",
        }
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process(PYTEST_OUTPUT_WITH_REGRESSION, returncode=1),
        ):
            result = await tool.execute(before_snapshot=before)
        assert result.metadata["net_gain"] == -1
        assert "-1" in result.output

    async def test_metadata_has_required_keys(self) -> None:
        tool = RegressionGuardTool()
        before = {"tests/unit/test_foo.py::test_alpha": "pass"}
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process(PYTEST_OUTPUT_NO_REGRESSION),
        ):
            result = await tool.execute(before_snapshot=before)
        assert "fixed" in result.metadata
        assert "regressed" in result.metadata
        assert "net_gain" in result.metadata

    async def test_empty_before_snapshot_all_failing_are_regressed(self) -> None:
        tool = RegressionGuardTool()
        # With empty before_snapshot, all currently failing tests count as regressed
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process(PYTEST_OUTPUT_WITH_REGRESSION, returncode=1),
        ):
            result = await tool.execute(before_snapshot={})
        assert result.success is False
        assert "tests/unit/test_bar.py::test_beta" in result.metadata["regressed"]
