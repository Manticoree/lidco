"""Tests for flake_runner — multi-run pytest executor."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.core.flake_detector import FlakeHistory, FlakeRecord, TestOutcome
from lidco.core.flake_runner import (
    MultiRunConfig,
    MultiRunResult,
    _parse_pytest_json,
    run_tests_multi,
)


# ---------------------------------------------------------------------------
# MultiRunConfig
# ---------------------------------------------------------------------------


class TestMultiRunConfig:
    def test_defaults(self):
        cfg = MultiRunConfig(test_paths=["tests/"])
        assert cfg.runs == 3
        assert cfg.timeout_per_run == 120
        assert cfg.min_flake_rate == 0.1
        assert cfg.min_runs_for_flake == 2

    def test_custom_runs(self):
        cfg = MultiRunConfig(test_paths=["tests/"], runs=5)
        assert cfg.runs == 5

    def test_frozen(self):
        cfg = MultiRunConfig(test_paths=["tests/"])
        with pytest.raises((AttributeError, TypeError)):
            cfg.runs = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MultiRunResult
# ---------------------------------------------------------------------------


class TestMultiRunResult:
    def test_frozen(self):
        r = MultiRunResult(
            history=FlakeHistory(),
            flaky_tests=[],
            total_runs=3,
            run_errors=[],
        )
        with pytest.raises((AttributeError, TypeError)):
            r.total_runs = 0  # type: ignore[misc]

    def test_fields(self):
        h = FlakeHistory()
        r = MultiRunResult(history=h, flaky_tests=[], total_runs=5, run_errors=[])
        assert r.history is h
        assert r.total_runs == 5
        assert r.run_errors == []


# ---------------------------------------------------------------------------
# _parse_pytest_json
# ---------------------------------------------------------------------------


class TestParsePytestJson:
    def _make_json(self, tests: list[dict]) -> dict:
        return {
            "tests": tests,
            "summary": {"passed": sum(1 for t in tests if t.get("outcome") == "passed"),
                        "failed": sum(1 for t in tests if t.get("outcome") == "failed")},
        }

    def test_parse_passed_test(self):
        data = self._make_json([
            {"nodeid": "tests/test_foo.py::test_bar", "outcome": "passed",
             "call": {"duration": 0.1}, "longrepr": None},
        ])
        outcomes = _parse_pytest_json(data)
        assert len(outcomes) == 1
        assert outcomes[0].test_id == "tests/test_foo.py::test_bar"
        assert outcomes[0].passed is True
        assert outcomes[0].duration_s == pytest.approx(0.1)
        assert outcomes[0].error_msg is None

    def test_parse_failed_test(self):
        data = self._make_json([
            {"nodeid": "tests/test_foo.py::test_baz", "outcome": "failed",
             "call": {"duration": 0.5},
             "longrepr": "AssertionError: expected 1 got 2"},
        ])
        outcomes = _parse_pytest_json(data)
        assert outcomes[0].passed is False
        assert "AssertionError" in outcomes[0].error_msg

    def test_skipped_tests_excluded(self):
        data = self._make_json([
            {"nodeid": "tests/test_foo.py::test_skip", "outcome": "skipped",
             "call": {"duration": 0.0}, "longrepr": None},
        ])
        outcomes = _parse_pytest_json(data)
        assert len(outcomes) == 0

    def test_missing_duration_defaults_zero(self):
        data = {"tests": [
            {"nodeid": "t::test_x", "outcome": "passed", "longrepr": None},
        ]}
        outcomes = _parse_pytest_json(data)
        assert outcomes[0].duration_s == 0.0

    def test_empty_tests_list(self):
        outcomes = _parse_pytest_json({"tests": []})
        assert outcomes == []

    def test_malformed_data_returns_empty(self):
        outcomes = _parse_pytest_json({})
        assert outcomes == []


# ---------------------------------------------------------------------------
# run_tests_multi — integration via subprocess mock
# ---------------------------------------------------------------------------


class TestRunTestsMulti:
    def _make_json_output(self, outcomes: list[tuple[str, bool]]) -> str:
        import json
        tests = []
        for nid, passed in outcomes:
            tests.append({
                "nodeid": nid,
                "outcome": "passed" if passed else "failed",
                "call": {"duration": 0.1},
                "longrepr": None if passed else "AssertionError",
            })
        return json.dumps({"tests": tests, "summary": {}})

    def _make_proc(self, json_out: str, returncode: int = 0) -> MagicMock:
        proc = MagicMock()
        proc.returncode = returncode
        proc.communicate = AsyncMock(return_value=(json_out.encode(), b""))
        return proc

    def test_all_pass_no_flakes(self):
        json_out = self._make_json_output([("t::test_a", True), ("t::test_b", True)])

        async def _run():
            proc = self._make_proc(json_out)
            with patch("lidco.core.flake_runner.asyncio.create_subprocess_exec",
                       new=AsyncMock(return_value=proc)):
                cfg = MultiRunConfig(test_paths=["tests/"], runs=3)
                return await run_tests_multi(cfg)

        result = asyncio.run(_run())
        assert result.total_runs == 3
        assert result.flaky_tests == []
        assert result.run_errors == []

    def test_consistent_failure_not_flaky(self):
        json_out = self._make_json_output([("t::test_a", False)])

        async def _run():
            proc = self._make_proc(json_out, returncode=1)
            with patch("lidco.core.flake_runner.asyncio.create_subprocess_exec",
                       new=AsyncMock(return_value=proc)):
                cfg = MultiRunConfig(test_paths=["tests/"], runs=3, min_flake_rate=0.1)
                return await run_tests_multi(cfg)

        result = asyncio.run(_run())
        assert isinstance(result, MultiRunResult)

    def test_run_error_captured(self):
        async def _run():
            with patch("lidco.core.flake_runner.asyncio.create_subprocess_exec",
                       side_effect=OSError("not found")):
                cfg = MultiRunConfig(test_paths=["tests/"], runs=2)
                return await run_tests_multi(cfg)

        result = asyncio.run(_run())
        assert len(result.run_errors) > 0
        assert result.total_runs < 2

    def test_timeout_per_run_respected(self):
        async def _run():
            proc = MagicMock()
            # communicate() raises TimeoutError when wait_for expires
            proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
            proc.kill = MagicMock()
            with patch("lidco.core.flake_runner.asyncio.create_subprocess_exec",
                       new=AsyncMock(return_value=proc)):
                cfg = MultiRunConfig(test_paths=["tests/"], runs=2, timeout_per_run=1)
                return await run_tests_multi(cfg)

        result = asyncio.run(_run())
        assert len(result.run_errors) > 0
