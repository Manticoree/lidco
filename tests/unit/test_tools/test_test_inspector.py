"""Tests for TestInspectorTool."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.test_inspector import TestInspectorTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_process(stdout: str, returncode: int = 1) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout.encode(), b""))
    return proc


# ---------------------------------------------------------------------------
# TestInspectorTool
# ---------------------------------------------------------------------------


class TestTestInspectorTool:
    def setup_method(self) -> None:
        self.tool = TestInspectorTool()

    # --- parsing locals ---

    async def test_parse_locals_simple_variable(self) -> None:
        output = (
            "tests/test_foo.py:10: in test_bar\n"
            "    result       = 42\n"
        )
        proc = _make_process(output)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(test_path="tests/test_foo.py")

        assert "result" in result.output
        assert "42" in result.output

    async def test_none_value_gets_warning_marker(self) -> None:
        output = (
            "tests/test_foo.py:15: in test_bar\n"
            "    data         = None\n"
        )
        proc = _make_process(output)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(test_path="tests/test_foo.py")

        assert "⚠" in result.output

    async def test_multiple_frames_parsed(self) -> None:
        output = (
            "tests/test_foo.py:10: in test_alpha\n"
            "    x            = 1\n"
            "tests/test_foo.py:20: in test_beta\n"
            "    y            = 2\n"
        )
        proc = _make_process(output)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(test_path="tests/test_foo.py")

        frames = result.metadata["frames"]
        assert len(frames) == 2

    async def test_empty_output_empty_locals(self) -> None:
        proc = _make_process("")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(test_path="tests/test_foo.py")

        assert result.metadata["frames"] == {}

    # --- timeout ---

    async def test_timeout_returns_graceful_result(self) -> None:
        proc = _make_process("")
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(test_path="tests/test_foo.py", timeout=1)

        assert result.success is False
        assert "timeout" in result.output.lower() or "timed out" in result.output.lower()

    # --- output header ---

    async def test_output_has_variable_state_header(self) -> None:
        output = (
            "tests/test_foo.py:5: in test_something\n"
            "    val          = 'hello'\n"
        )
        proc = _make_process(output)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(test_path="tests/test_foo.py")

        assert "## Variable State at Failure" in result.output

    # --- metadata frames ---

    async def test_metadata_has_frames_dict(self) -> None:
        proc = _make_process("")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(test_path="tests/test_foo.py")

        assert "frames" in result.metadata
        assert isinstance(result.metadata["frames"], dict)

    # --- multiple vars in same frame ---

    async def test_multiple_vars_in_same_frame(self) -> None:
        output = (
            "tests/test_foo.py:30: in test_multi\n"
            "    alpha        = 10\n"
            "    beta         = 20\n"
            "    gamma        = 30\n"
        )
        proc = _make_process(output)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(test_path="tests/test_foo.py")

        frames = result.metadata["frames"]
        assert len(frames) == 1
        frame_vars = list(frames.values())[0]
        assert len(frame_vars) == 3
        assert "alpha" in frame_vars
        assert "beta" in frame_vars
        assert "gamma" in frame_vars

    # --- var name with underscores ---

    async def test_var_name_with_underscores(self) -> None:
        output = (
            "tests/test_foo.py:5: in test_under\n"
            "    my_var_name  = 'value'\n"
        )
        proc = _make_process(output)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(test_path="tests/test_foo.py")

        frames = result.metadata["frames"]
        frame_vars = list(frames.values())[0]
        assert "my_var_name" in frame_vars

    # --- success always False ---

    async def test_success_always_false(self) -> None:
        proc = _make_process("5 passed in 0.1s", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(test_path="tests/test_foo.py")

        assert result.success is False
