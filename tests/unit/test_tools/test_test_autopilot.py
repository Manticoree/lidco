"""Tests for TestAutopilotTool and _parse_failed_count."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.test_autopilot import TestAutopilotTool, _parse_failed_count


# ---------------------------------------------------------------------------
# _parse_failed_count
# ---------------------------------------------------------------------------


def test_parse_failed_count_finds_number() -> None:
    assert _parse_failed_count("5 failed, 3 passed in 1.2s") == 5


def test_parse_failed_count_returns_zero_on_no_match() -> None:
    assert _parse_failed_count("all passing, nothing wrong") == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_process(stdout: str, returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout.encode(), b""))
    return proc


# ---------------------------------------------------------------------------
# TestAutopilotTool
# ---------------------------------------------------------------------------


class TestTestAutopilotTool:
    def setup_method(self) -> None:
        self.tool = TestAutopilotTool()

    # --- all tests passing ---

    async def test_all_passing_returns_no_cycle_needed(self) -> None:
        proc = _make_process("10 passed in 0.5s", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run()
        assert "All tests passing" in result.output

    async def test_all_passing_success_is_true(self) -> None:
        proc = _make_process("10 passed in 0.5s", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run()
        assert result.success is True

    # --- threshold not met ---

    async def test_threshold_not_met_success_is_false(self) -> None:
        # baseline: 10 failing; each subsequent run: still 10 failing → stall
        proc = _make_process("10 failed in 1.0s", returncode=1)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run(max_rounds=3, confidence_threshold=0.8)
        assert result.success is False

    # --- max_rounds respected ---

    async def test_max_rounds_metadata(self) -> None:
        # baseline: 5 failing; subsequent runs: 4, 3, 2 failing (never hits 0.8 of 5=4)
        outputs = ["5 failed", "4 failed", "3 failed", "2 failed"]
        call_count = 0

        async def fake_exec(*args, **kwargs):  # noqa: ANN001
            nonlocal call_count
            text = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(text.encode(), b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await self.tool._run(max_rounds=3, confidence_threshold=0.95)

        assert result.metadata["rounds"] == 3

    # --- stall detection ---

    async def test_stall_breaks_early(self) -> None:
        # baseline: 5 failing; next run also 5 failing → stall after round 1
        outputs = ["5 failed", "5 failed"]
        call_count = 0

        async def fake_exec(*args, **kwargs):  # noqa: ANN001
            nonlocal call_count
            text = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(text.encode(), b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await self.tool._run(max_rounds=3, confidence_threshold=0.8)

        assert result.metadata["rounds"] == 1

    # --- confidence calculation ---

    async def test_confidence_calculation(self) -> None:
        # baseline: 10 failing; next run: 2 failing → 8 fixed = 0.8 confidence
        outputs = ["10 failed", "2 failed"]
        call_count = 0

        async def fake_exec(*args, **kwargs):  # noqa: ANN001
            nonlocal call_count
            text = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(text.encode(), b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await self.tool._run(max_rounds=3, confidence_threshold=0.8)

        assert result.metadata["confidence"] == pytest.approx(0.8)

    # --- round summary format ---

    async def test_round_summary_in_output(self) -> None:
        outputs = ["5 failed", "3 failed"]
        call_count = 0

        async def fake_exec(*args, **kwargs):  # noqa: ANN001
            nonlocal call_count
            text = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(text.encode(), b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await self.tool._run(max_rounds=3, confidence_threshold=0.9)

        assert "Round 1:" in result.output

    # --- metadata fields ---

    async def test_metadata_has_originally_failing(self) -> None:
        outputs = ["7 failed", "7 failed"]
        call_count = 0

        async def fake_exec(*args, **kwargs):  # noqa: ANN001
            nonlocal call_count
            text = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(text.encode(), b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await self.tool._run(max_rounds=1)

        assert result.metadata["originally_failing"] == 7

    async def test_metadata_has_confidence(self) -> None:
        proc = _make_process("10 passed in 0.5s", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await self.tool._run()
        assert "confidence" in result.metadata

    # --- empty test_path ---

    async def test_empty_test_path_passes_no_path_arg(self) -> None:
        proc = _make_process("5 passed in 0.5s", returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await self.tool._run(test_path="")
        cmd = mock_exec.call_args[0]
        # With empty test_path the command should not include a path argument
        # (only python, -m, pytest, -q)
        assert "" not in cmd
