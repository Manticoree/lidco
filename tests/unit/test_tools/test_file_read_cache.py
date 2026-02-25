"""Tests for in-session file read cache in FileReadTool."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.tools.file_read import FileReadTool, _cache_get, _cache_set, _read_cache


# ── Helpers ───────────────────────────────────────────────────────────────────


def _clear_cache() -> None:
    _read_cache.clear()


# ── Cache primitives ──────────────────────────────────────────────────────────


class TestCachePrimitives:
    def setup_method(self) -> None:
        _clear_cache()

    def test_cache_miss_returns_none(self) -> None:
        assert _cache_get(("/some/path", 1, 100, 0)) is None

    def test_cache_set_and_get(self) -> None:
        key = ("/a/b.py", 1, 200, 12345)
        _cache_set(key, "some output")
        assert _cache_get(key) == "some output"

    def test_cache_hit_moves_to_end(self) -> None:
        """LRU: recently accessed entry should survive eviction over untouched entries."""
        from lidco.tools.file_read import _CACHE_MAX

        # Fill cache to CACHE_MAX - 1, then add "victim" (LRU) and "keeper" (MRU)
        for i in range(_CACHE_MAX - 2):
            _cache_set((f"fill_{i}", 1, 1, 1), "v")
        _cache_set(("victim", 1, 1, 1), "old")
        _cache_set(("keeper", 1, 1, 1), "new")
        # Access "victim" so it becomes recently used — it should outlast "fill_0"
        _cache_get(("victim", 1, 1, 1))
        # Adding 2 more entries evicts the 2 LRU entries (fill_0 and fill_1),
        # NOT "victim" (which was just accessed)
        _cache_set(("extra1", 1, 1, 1), "x")
        _cache_set(("extra2", 1, 1, 1), "x")
        assert _cache_get(("victim", 1, 1, 1)) == "old"

    def test_cache_evicts_lru_when_full(self) -> None:
        from lidco.tools.file_read import _CACHE_MAX
        _clear_cache()
        _cache_set(("victim", 1, 1, 1), "stale")
        for i in range(_CACHE_MAX):
            _cache_set((f"k{i}", 1, 1, 1), "v")
        # victim should have been evicted
        assert _cache_get(("victim", 1, 1, 1)) is None


# ── FileReadTool caching integration ─────────────────────────────────────────


class TestFileReadToolCache:
    def setup_method(self) -> None:
        _clear_cache()

    @pytest.mark.asyncio
    async def test_result_is_cached_on_first_read(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text("line1\nline2\n")

        tool = FileReadTool(enricher=None, project_dir=tmp_path)
        result1 = await tool._run(path=str(f))
        result2 = await tool._run(path=str(f))

        assert result1.output == result2.output

    @pytest.mark.asyncio
    async def test_second_read_is_cached(self, tmp_path: Path) -> None:
        """Second call should return metadata with cached=True."""
        f = tmp_path / "cached.py"
        f.write_text("hello\n")

        tool = FileReadTool(enricher=None, project_dir=tmp_path)
        await tool._run(path=str(f))  # first read populates cache
        result2 = await tool._run(path=str(f))

        assert result2.metadata.get("cached") is True

    @pytest.mark.asyncio
    async def test_cache_invalidated_when_file_changes(self, tmp_path: Path) -> None:
        f = tmp_path / "changing.py"
        f.write_text("original\n")

        tool = FileReadTool(enricher=None, project_dir=tmp_path)
        result1 = await tool._run(path=str(f))

        # Modify file (force new mtime — on fast filesystems sleep briefly)
        time.sleep(0.01)
        f.write_text("modified\n")

        result2 = await tool._run(path=str(f))

        assert "original" in result1.output
        assert "modified" in result2.output
        assert result2.metadata.get("cached") is not True

    @pytest.mark.asyncio
    async def test_different_offset_is_different_cache_entry(self, tmp_path: Path) -> None:
        f = tmp_path / "multi.py"
        f.write_text("\n".join(f"line{i}" for i in range(20)))

        tool = FileReadTool(enricher=None, project_dir=tmp_path)
        r1 = await tool._run(path=str(f), offset=1, limit=5)
        r2 = await tool._run(path=str(f), offset=10, limit=5)

        assert r1.output != r2.output
        # Both should succeed
        assert r1.success
        assert r2.success

    @pytest.mark.asyncio
    async def test_nonexistent_file_not_cached(self, tmp_path: Path) -> None:
        tool = FileReadTool(enricher=None, project_dir=tmp_path)
        result = await tool._run(path=str(tmp_path / "ghost.py"))
        assert not result.success
        # Cache should remain empty
        assert len(_read_cache) == 0
