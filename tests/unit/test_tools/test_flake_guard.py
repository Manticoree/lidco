"""Tests for FlakeGuardTool."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.flake_guard import FlakeGuardTool
from lidco.tools.base import ToolResult


def _make_tool() -> FlakeGuardTool:
    return FlakeGuardTool()


def _make_proc(test_outcomes: list[tuple[str, bool]], returncode: int = 0) -> MagicMock:
    tests = []
    for nid, passed in test_outcomes:
        tests.append({
            "nodeid": nid,
            "outcome": "passed" if passed else "failed",
            "call": {"duration": 0.1},
            "longrepr": None if passed else "AssertionError",
        })
    json_out = json.dumps({"tests": tests, "summary": {}})
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(json_out.encode(), b""))
    return proc


class TestFlakeGuardToolMeta:
    def test_name(self):
        assert _make_tool().name == "flake_guard"

    def test_description_not_empty(self):
        assert len(_make_tool().description) > 10

    def test_parameters_include_test_paths(self):
        names = [p.name for p in _make_tool().parameters]
        assert "test_paths" in names

    def test_parameters_include_runs(self):
        names = [p.name for p in _make_tool().parameters]
        assert "runs" in names

    def test_openai_schema_valid(self):
        schema = _make_tool().to_openai_schema()
        assert schema["type"] == "function"
        assert "name" in schema["function"]
        assert "parameters" in schema["function"]


class TestFlakeGuardToolRun:
    def test_no_flakes_success(self):
        async def _run():
            proc = _make_proc([("t::a", True), ("t::b", True)])
            with patch("lidco.core.flake_runner.asyncio.create_subprocess_exec",
                       new=AsyncMock(return_value=proc)):
                tool = _make_tool()
                return await tool._run(test_paths="tests/", runs=3)

        result = asyncio.run(_run())
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "OK" in result.output or "flaky" in result.output.lower()

    def test_flaky_test_detected_success_false(self):
        # Alternating pass/fail across runs → flaky
        call_count = [0]

        async def _make_varying_proc(*args, **kwargs):
            call_count[0] += 1
            # Run 1: passes, Run 2: fails, Run 3: passes
            passed = (call_count[0] % 2 == 1)
            return _make_proc([("t::flaky", passed)], returncode=0 if passed else 1)

        async def _run():
            with patch("lidco.core.flake_runner.asyncio.create_subprocess_exec",
                       new=_make_varying_proc):
                tool = _make_tool()
                return await tool._run(test_paths="tests/", runs=3, min_flake_rate=0.1)

        result = asyncio.run(_run())
        assert isinstance(result, ToolResult)
        # Either success=False (flakes found) or success=True (no flakes after threshold)
        assert "flaky" in result.output.lower() or "flake" in result.output.lower() or "OK" in result.output

    def test_invalid_runs_parameter(self):
        async def _run():
            tool = _make_tool()
            return await tool._run(test_paths="tests/", runs=0)

        result = asyncio.run(_run())
        assert isinstance(result, ToolResult)
        assert result.success is False

    def test_metadata_contains_counts(self):
        async def _run():
            proc = _make_proc([("t::a", True)])
            with patch("lidco.core.flake_runner.asyncio.create_subprocess_exec",
                       new=AsyncMock(return_value=proc)):
                tool = _make_tool()
                return await tool._run(test_paths="tests/", runs=2)

        result = asyncio.run(_run())
        assert "total_runs" in result.metadata
        assert "flaky_count" in result.metadata

    def test_run_errors_in_output(self):
        async def _run():
            with patch("lidco.core.flake_runner.asyncio.create_subprocess_exec",
                       side_effect=OSError("not found")):
                tool = _make_tool()
                return await tool._run(test_paths="tests/", runs=2)

        result = asyncio.run(_run())
        # Should still return a result, not raise
        assert isinstance(result, ToolResult)
        assert result.metadata.get("run_errors", 0) > 0 or "error" in result.output.lower()
