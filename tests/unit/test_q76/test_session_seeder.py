"""Tests for SessionSeeder — T504."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lidco.memory.session_seeder import SeedContext, SessionSeeder


def _make_memory(content: str, tags: list[str] | None = None):
    m = MagicMock()
    m.content = content
    m.tags = tags or []
    m.id = content[:8]
    return m


def _make_store(ws_memories=None, global_memories=None):
    """Create a mock TieredMemoryStore."""
    store = MagicMock()
    ws = MagicMock()
    gl = MagicMock()

    ws_mems = ws_memories or []
    gl_mems = global_memories or []

    ws.search = MagicMock(return_value=ws_mems)
    gl.search = MagicMock(return_value=gl_mems)

    store.workspace_store = ws
    store.global_store = gl

    # TieredMemoryStore.search returns combined
    all_mems = ws_mems + [m for m in gl_mems if m.content not in {x.content for x in ws_mems}]
    store.search = MagicMock(return_value=all_mems)

    return store


class TestSeed:
    def test_seed_returns_seed_context(self):
        mem = _make_memory("remember this")
        store = _make_store(ws_memories=[mem])
        seeder = SessionSeeder(memory_store=store)
        ctx = seeder.seed(project_name="test")
        assert isinstance(ctx, SeedContext)
        assert len(ctx.memories) == 1

    def test_seed_respects_token_budget(self):
        # Create memories with long content
        mems = [_make_memory("x" * 500) for _ in range(10)]
        store = _make_store(ws_memories=mems)
        seeder = SessionSeeder(memory_store=store, token_budget=50)
        ctx = seeder.seed()
        # prompt_block should be truncated
        assert len(ctx.prompt_block) <= 50 * 4 + 100  # some header overhead

    def test_seed_with_tags_filter(self):
        m1 = _make_memory("tagged memory", tags=["python"])
        m2 = _make_memory("untagged memory", tags=[])
        store = _make_store(ws_memories=[m1, m2])
        seeder = SessionSeeder(memory_store=store, tags_filter=["python"])
        ctx = seeder.seed()
        # Only m1 should pass the filter
        assert all(
            "python" in getattr(m, "tags", []) for m in ctx.memories
        )

    def test_seed_with_recent_files(self):
        mem = _make_memory("file memory")
        store = _make_store(ws_memories=[mem])
        # recent_files triggers extra searches
        seeder = SessionSeeder(memory_store=store)
        ctx = seeder.seed(recent_files=["main.py", "utils.py"])
        # workspace_store.search should have been called for each file
        assert store.workspace_store.search.call_count >= 3  # project + 2 files

    def test_source_workspace_only(self):
        mem = _make_memory("ws mem")
        store = _make_store(ws_memories=[mem], global_memories=[])
        seeder = SessionSeeder(memory_store=store)
        ctx = seeder.seed()
        assert ctx.source == "workspace"

    def test_source_global_only(self):
        mem = _make_memory("global mem")
        store = _make_store(ws_memories=[], global_memories=[mem])
        seeder = SessionSeeder(memory_store=store)
        ctx = seeder.seed()
        assert ctx.source == "global"

    def test_source_both_when_both_have_results(self):
        ws_mem = _make_memory("ws content")
        gl_mem = _make_memory("global content")
        store = _make_store(ws_memories=[ws_mem], global_memories=[gl_mem])
        seeder = SessionSeeder(memory_store=store)
        ctx = seeder.seed()
        assert ctx.source == "both"


class TestFormatMemories:
    def test_format_truncation(self):
        mems = [_make_memory("x" * 200) for _ in range(10)]
        seeder = SessionSeeder(memory_store=MagicMock(), token_budget=2048)
        result = seeder.format_memories(mems, budget=10)
        # Budget is 10 tokens = 40 chars; header alone is ~11 chars
        assert len(result) <= 10 * 4 + 20  # header + a bit of slack


class TestShouldSeed:
    def test_should_seed_true_when_results(self):
        mem = _make_memory("something")
        store = _make_store(ws_memories=[mem])
        seeder = SessionSeeder(memory_store=store)
        assert seeder.should_seed() is True

    def test_should_seed_false_when_empty(self):
        store = MagicMock()
        store.search = MagicMock(return_value=[])
        seeder = SessionSeeder(memory_store=store)
        assert seeder.should_seed() is False
