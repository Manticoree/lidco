"""Tests for StaticAnalyzerTool."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.static_analyzer import StaticAnalyzerTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_process(stdout: str, returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout.encode(), b""))
    return proc


def _ruff_json(items: list[dict]) -> str:
    return json.dumps(items)


# ---------------------------------------------------------------------------
# StaticAnalyzerTool
# ---------------------------------------------------------------------------


class TestStaticAnalyzerTool:
    def setup_method(self) -> None:
        self.tool = StaticAnalyzerTool()

    # --- ruff parsing ---

    async def test_ruff_json_parsed_correctly(self) -> None:
        payload = [
            {
                "filename": "src/foo.py",
                "location": {"row": 10, "column": 5},
                "code": "E501",
                "message": "line too long",
            }
        ]
        ruff_proc = _make_process(_ruff_json(payload))
        # mypy returns nothing
        mypy_proc = _make_process("")

        call_count = 0

        async def fake_exec(*args, **kwargs):  # noqa: ANN001
            nonlocal call_count
            call_count += 1
            return ruff_proc if call_count == 1 else mypy_proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await self.tool._run(checks=["ruff"])

        assert result.metadata["total"] == 1
        issue = result.metadata["issues"][0]
        assert issue["file"] == "src/foo.py"
        assert issue["line"] == 10
        assert issue["severity"] == "ERROR"
        assert issue["rule"] == "E501"

    # --- mypy parsing ---

    async def test_mypy_line_parsed_correctly(self) -> None:
        mypy_out = "src/bar.py:20: error: Argument 1 to 'foo' [arg-type]\n"
        mypy_proc = _make_process(mypy_out, returncode=1)

        with patch("asyncio.create_subprocess_exec", return_value=mypy_proc):
            result = await self.tool._run(checks=["mypy"])

        assert result.metadata["total"] >= 1
        issue = result.metadata["issues"][0]
        assert issue["file"] == "src/bar.py"
        assert issue["line"] == 20
        assert issue["severity"] == "ERROR"
        assert issue["rule"] == "arg-type"

    # --- empty ruff output ---

    async def test_empty_ruff_output_zero_issues(self) -> None:
        proc = _make_process("")

        async def fake_exec(*args, **kwargs):  # noqa: ANN001
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await self.tool._run(checks=["ruff"])

        assert result.metadata["total"] == 0

    # --- cap at 50 ---

    async def test_issues_capped_at_50(self) -> None:
        payload = [
            {
                "filename": f"src/file{i}.py",
                "location": {"row": i, "column": 0},
                "code": "W291",
                "message": "trailing whitespace",
            }
            for i in range(60)
        ]
        ruff_proc = _make_process(_ruff_json(payload))

        with patch("asyncio.create_subprocess_exec", return_value=ruff_proc):
            result = await self.tool._run(checks=["ruff"])

        assert len(result.metadata["issues"]) == 50

    # --- success based on errors ---

    async def test_no_errors_success_true(self) -> None:
        # Warning only (W code)
        payload = [
            {
                "filename": "src/foo.py",
                "location": {"row": 1, "column": 0},
                "code": "W291",
                "message": "trailing whitespace",
            }
        ]
        proc = _make_process(_ruff_json(payload))
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(checks=["ruff"])

        assert result.success is True

    async def test_errors_present_success_false(self) -> None:
        payload = [
            {
                "filename": "src/foo.py",
                "location": {"row": 1, "column": 0},
                "code": "E501",
                "message": "line too long",
            }
        ]
        proc = _make_process(_ruff_json(payload))
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(checks=["ruff"])

        assert result.success is False

    # --- metadata fields ---

    async def test_metadata_has_required_fields(self) -> None:
        proc = _make_process("")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(checks=["ruff"])

        assert "total" in result.metadata
        assert "errors" in result.metadata
        assert "warnings" in result.metadata

    # --- ruff not found ---

    async def test_ruff_not_found_graceful(self) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await self.tool._run(checks=["ruff"])

        assert result.metadata["total"] == 0

    # --- fix flag ---

    async def test_fix_flag_passed_to_ruff(self) -> None:
        proc = _make_process("[]")
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await self.tool._run(checks=["ruff"], fix=True)

        cmd = mock_exec.call_args[0]
        assert "--fix" in cmd

    # --- checks=["ruff"] skips mypy ---

    async def test_ruff_only_skips_mypy(self) -> None:
        proc = _make_process("[]")
        call_count = 0

        async def fake_exec(*args, **kwargs):  # noqa: ANN001
            nonlocal call_count
            call_count += 1
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await self.tool._run(checks=["ruff"])

        # Only one subprocess call (ruff), not two (ruff + mypy)
        assert call_count == 1
