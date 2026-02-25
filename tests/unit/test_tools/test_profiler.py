"""Tests for ProfilerTool and the _run_async_streaming helper."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.profiler import ProfilerTool, _run_async_streaming


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_subprocess_result(returncode: int = 0, stderr: str = "") -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stderr = stderr
    result.stdout = ""
    return result


def _make_streaming_process(lines: list[str], returncode: int = 0) -> MagicMock:
    """Build a mock async subprocess that yields *lines* from readline()."""
    proc = MagicMock()
    proc.returncode = returncode

    encoded = [l.encode() for l in lines] + [b""]

    async def _readline() -> bytes:
        return encoded.pop(0)

    stdout_mock = MagicMock()
    stdout_mock.readline = _readline
    proc.stdout = stdout_mock

    stderr_mock = MagicMock()
    stderr_mock.read = AsyncMock(return_value=b"")
    proc.stderr = stderr_mock

    proc.wait = AsyncMock()
    return proc


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestProfilerToolMetadata:
    def test_name(self) -> None:
        assert ProfilerTool().name == "run_profiler"

    def test_has_five_parameters(self) -> None:
        names = {p.name for p in ProfilerTool().parameters}
        assert names == {"script", "args", "sort_by", "top_n", "stream_output"}

    def test_stream_output_param_not_required(self) -> None:
        param = next(p for p in ProfilerTool().parameters if p.name == "stream_output")
        assert param.required is False
        assert param.default is False


# ---------------------------------------------------------------------------
# _run_async_streaming helper
# ---------------------------------------------------------------------------

class TestRunAsyncStreaming:
    @pytest.mark.asyncio
    async def test_calls_callback_per_line(self) -> None:
        lines = ["Starting...\n", "Done.\n"]
        proc = _make_streaming_process(lines, returncode=0)
        received: list[str] = []

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            rc, stderr = await _run_async_streaming(
                ["python", "script.py"], received.append
            )

        assert rc == 0
        assert received == ["Starting...", "Done."]
        assert stderr == ""

    @pytest.mark.asyncio
    async def test_returns_returncode_and_stderr(self) -> None:
        proc = _make_streaming_process([], returncode=1)
        proc.stderr.read = AsyncMock(return_value=b"some error\n")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            rc, stderr = await _run_async_streaming(["cmd"], lambda _: None)

        assert rc == 1
        assert "some error" in stderr

    @pytest.mark.asyncio
    async def test_timeout_raises(self) -> None:
        proc = MagicMock()
        proc.stdout = MagicMock()
        proc.stdout.readline = AsyncMock(side_effect=asyncio.TimeoutError)
        proc.stderr = MagicMock()
        proc.stderr.read = AsyncMock(return_value=b"")
        proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(asyncio.TimeoutError):
                await _run_async_streaming(["cmd"], lambda _: None, timeout=1)


# ---------------------------------------------------------------------------
# ProfilerTool._run() — non-streaming (existing behavior)
# ---------------------------------------------------------------------------

class TestProfilerToolRun:
    def setup_method(self) -> None:
        self.tool = ProfilerTool()

    @pytest.mark.asyncio
    async def test_inline_code_uses_temp_file(self, tmp_path: Path) -> None:
        """Inline code (not a real path) is written to a temp .py file."""
        subprocess_result = _make_subprocess_result(returncode=0)
        fake_stats_file = tmp_path / "fake.prof"
        fake_stats_file.write_bytes(b"")

        with (
            patch("subprocess.run", return_value=subprocess_result),
            patch("tempfile.mktemp", return_value=str(fake_stats_file)),
            patch("pstats.Stats") as mock_stats,
        ):
            mock_stats.return_value.sort_stats.return_value = MagicMock()
            mock_stats.return_value.print_stats = MagicMock()
            result = await self.tool._run(script="print('hello')")

        # Should not raise; profile output may be empty but no error
        assert isinstance(result.output, str)

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self) -> None:
        import subprocess

        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="cmd", timeout=60)
        ):
            result = await self.tool._run(script="print(1)")

        assert result.success is False
        assert "timed out" in result.output.lower()

    @pytest.mark.asyncio
    async def test_stream_false_uses_sync_subprocess(self) -> None:
        subprocess_result = _make_subprocess_result(returncode=0)
        with (
            patch("subprocess.run", return_value=subprocess_result) as mock_run,
            patch("tempfile.mktemp", return_value="/tmp/x.prof"),
            patch("pstats.Stats", side_effect=Exception("no stats")),
        ):
            await self.tool._run(script="x=1", stream_output=False)

        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_true_without_callback_uses_sync(self) -> None:
        """When stream_output=True but no callback set, falls back to subprocess.run."""
        subprocess_result = _make_subprocess_result(returncode=0)
        with (
            patch("subprocess.run", return_value=subprocess_result) as mock_run,
            patch("tempfile.mktemp", return_value="/tmp/x.prof"),
            patch("pstats.Stats", side_effect=Exception("no stats")),
        ):
            await self.tool._run(script="x=1", stream_output=True)

        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# ProfilerTool._run() — streaming path
# ---------------------------------------------------------------------------

class TestProfilerToolStreaming:
    def setup_method(self) -> None:
        self.tool = ProfilerTool()

    @pytest.mark.asyncio
    async def test_stream_calls_callback_per_line(self, tmp_path: Path) -> None:
        lines = ["Running...\n", "Value: 42\n"]
        proc = _make_streaming_process(lines, returncode=0)
        fake_stats_file = tmp_path / "fake.prof"
        fake_stats_file.write_bytes(b"")
        received: list[str] = []
        self.tool.set_progress_callback(received.append)

        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("tempfile.mktemp", return_value=str(fake_stats_file)),
            patch("pstats.Stats", side_effect=Exception("no stats")),
        ):
            await self.tool._run(script="print('hi')", stream_output=True)

        assert received == ["Running...", "Value: 42"]

    @pytest.mark.asyncio
    async def test_stream_does_not_call_sync_subprocess(self, tmp_path: Path) -> None:
        lines: list[str] = []
        proc = _make_streaming_process(lines, returncode=0)
        fake_stats_file = tmp_path / "fake.prof"
        fake_stats_file.write_bytes(b"")
        self.tool.set_progress_callback(lambda _: None)

        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("subprocess.run") as mock_sync,
            patch("tempfile.mktemp", return_value=str(fake_stats_file)),
            patch("pstats.Stats", side_effect=Exception("no stats")),
        ):
            await self.tool._run(script="x=1", stream_output=True)

        mock_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_stream_timeout_returns_error(self) -> None:
        proc = MagicMock()
        proc.stdout = MagicMock()
        proc.stdout.readline = AsyncMock(side_effect=asyncio.TimeoutError)
        proc.stderr = MagicMock()
        proc.stderr.read = AsyncMock(return_value=b"")
        proc.wait = AsyncMock()
        self.tool.set_progress_callback(lambda _: None)

        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("tempfile.mktemp", return_value="/tmp/x.prof"),
        ):
            result = await self.tool._run(script="x=1", stream_output=True)

        assert result.success is False
        assert "timed out" in result.output.lower()
