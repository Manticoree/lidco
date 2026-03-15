"""Tests for MemoryCompressor — Task 313."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.context.memory_compressor import CompressionResult, MemoryCompressor


def _mock_session(summary: str = "compressed summary") -> MagicMock:
    session = MagicMock()
    resp = MagicMock()
    resp.content = summary
    session.llm.complete = AsyncMock(return_value=resp)
    return session


# ---------------------------------------------------------------------------
# CompressionResult
# ---------------------------------------------------------------------------

class TestCompressionResult:
    def test_lines_saved(self):
        r = CompressionResult(
            compressed=True,
            original_lines=500,
            new_lines=100,
        )
        assert r.lines_saved == 400

    def test_no_compression(self):
        r = CompressionResult(compressed=False, original_lines=200, new_lines=200)
        assert r.lines_saved == 0


# ---------------------------------------------------------------------------
# maybe_compress — under threshold
# ---------------------------------------------------------------------------

class TestMaybeCompressUnderThreshold:
    def test_file_under_threshold_not_compressed(self, tmp_path):
        path = tmp_path / "MEMORY.md"
        path.write_text("line\n" * 100, encoding="utf-8")
        compressor = MemoryCompressor(session=None, threshold_lines=500)
        result = asyncio.run(compressor.maybe_compress(path))
        assert result.compressed is False

    def test_missing_file_returns_not_compressed(self, tmp_path):
        path = tmp_path / "missing.md"
        compressor = MemoryCompressor(session=None)
        result = asyncio.run(compressor.maybe_compress(path))
        assert result.compressed is False

    def test_custom_threshold(self, tmp_path):
        path = tmp_path / "mem.md"
        path.write_text("x\n" * 20, encoding="utf-8")
        compressor = MemoryCompressor(session=_mock_session(), threshold_lines=10)
        result = asyncio.run(compressor.maybe_compress(path))
        assert result.compressed is True


# ---------------------------------------------------------------------------
# maybe_compress — at/over threshold
# ---------------------------------------------------------------------------

class TestMaybeCompressOverThreshold:
    def test_compresses_when_over_threshold(self, tmp_path):
        path = tmp_path / "MEMORY.md"
        path.write_text("entry\n" * 600, encoding="utf-8")
        compressor = MemoryCompressor(
            session=_mock_session("summary text"),
            threshold_lines=500,
            keep_recent_lines=50,
        )
        result = asyncio.run(compressor.maybe_compress(path))
        assert result.compressed is True
        assert result.original_lines == 600

    def test_compressed_file_contains_summary(self, tmp_path):
        path = tmp_path / "MEMORY.md"
        path.write_text("old entry\n" * 600, encoding="utf-8")
        compressor = MemoryCompressor(
            session=_mock_session("the compressed summary"),
            threshold_lines=100,
            keep_recent_lines=20,
        )
        asyncio.run(compressor.maybe_compress(path))
        content = path.read_text(encoding="utf-8")
        assert "the compressed summary" in content

    def test_compressed_file_smaller(self, tmp_path):
        path = tmp_path / "MEMORY.md"
        path.write_text("line\n" * 600, encoding="utf-8")
        compressor = MemoryCompressor(
            session=_mock_session("short summary"),
            threshold_lines=500,
            keep_recent_lines=50,
        )
        result = asyncio.run(compressor.maybe_compress(path))
        assert result.new_lines < result.original_lines

    def test_keeps_recent_lines(self, tmp_path):
        path = tmp_path / "MEMORY.md"
        # Write 600 lines where the last 50 are distinctive
        old_lines = ["old_entry\n"] * 550
        recent_lines = ["RECENT_LINE\n"] * 50
        path.write_text("".join(old_lines + recent_lines), encoding="utf-8")

        compressor = MemoryCompressor(
            session=_mock_session("summary"),
            threshold_lines=500,
            keep_recent_lines=50,
        )
        asyncio.run(compressor.maybe_compress(path))
        content = path.read_text(encoding="utf-8")
        assert "RECENT_LINE" in content


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestMaybeCompressErrors:
    def test_llm_failure_returns_error_result(self, tmp_path):
        path = tmp_path / "MEMORY.md"
        path.write_text("line\n" * 600, encoding="utf-8")

        session = MagicMock()
        session.llm.complete = AsyncMock(side_effect=RuntimeError("API down"))

        compressor = MemoryCompressor(
            session=session,
            threshold_lines=500,
        )
        result = asyncio.run(compressor.maybe_compress(path))
        assert result.compressed is False
        assert "API down" in result.error

    def test_no_session_returns_error(self, tmp_path):
        path = tmp_path / "MEMORY.md"
        path.write_text("line\n" * 600, encoding="utf-8")

        compressor = MemoryCompressor(session=None, threshold_lines=100)
        result = asyncio.run(compressor.maybe_compress(path))
        assert result.compressed is False
        assert result.error
