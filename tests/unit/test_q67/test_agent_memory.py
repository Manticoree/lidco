"""Tests for Q67 Task 452 -- Persistent Agent Memory."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture: create an AgentMemoryStore backed by a temp SQLite DB
# ---------------------------------------------------------------------------
@pytest.fixture()
def store(tmp_path: Path):
    from lidco.memory.agent_memory import AgentMemoryStore

    return AgentMemoryStore(db_path=tmp_path / "test_memory.db")


# ---------------------------------------------------------------------------
# 1. test_add_returns_memory
# ---------------------------------------------------------------------------
class TestAddReturnsMemory:
    """add() should return an AgentMemory with id, content, timestamps."""

    def test_add_returns_memory(self, store):
        from lidco.memory.agent_memory import AgentMemory

        mem = store.add("Always use immutable patterns")
        assert isinstance(mem, AgentMemory)
        assert mem.id
        assert mem.content == "Always use immutable patterns"
        assert mem.created_at > 0
        assert mem.last_used > 0
        assert mem.use_count == 0
        assert mem.tags == []

    def test_add_strips_whitespace(self, store):
        mem = store.add("  padded content  ")
        assert mem.content == "padded content"


# ---------------------------------------------------------------------------
# 2. test_list_returns_most_recent_first
# ---------------------------------------------------------------------------
class TestListReturnsMostRecentFirst:
    """list() should return memories ordered by last_used descending."""

    def test_list_ordering(self, store):
        store.add("first memory")
        time.sleep(0.01)
        store.add("second memory")
        time.sleep(0.01)
        store.add("third memory")

        memories = store.list()
        assert len(memories) == 3
        assert memories[0].content == "third memory"
        assert memories[2].content == "first memory"

    def test_list_respects_limit(self, store):
        for i in range(5):
            store.add(f"memory {i}")
        memories = store.list(limit=2)
        assert len(memories) == 2


# ---------------------------------------------------------------------------
# 3. test_search_finds_keyword
# ---------------------------------------------------------------------------
class TestSearchFindsKeyword:
    """search() should find memories containing the keyword."""

    def test_search_by_content(self, store):
        store.add("deploy to production")
        store.add("run unit tests")
        store.add("deploy to staging")

        results = store.search("deploy")
        assert len(results) == 2
        for r in results:
            assert "deploy" in r.content.lower()

    def test_search_case_insensitive(self, store):
        store.add("Deploy with Docker")
        results = store.search("deploy")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# 4. test_search_returns_empty_for_no_match
# ---------------------------------------------------------------------------
class TestSearchReturnsEmptyForNoMatch:
    """search() should return empty list when nothing matches."""

    def test_no_match(self, store):
        store.add("some content")
        results = store.search("xyznonexistent")
        assert results == []

    def test_search_empty_store(self, store):
        results = store.search("anything")
        assert results == []


# ---------------------------------------------------------------------------
# 5. test_delete_removes_memory
# ---------------------------------------------------------------------------
class TestDeleteRemovesMemory:
    """delete(id) should remove the memory; get(id) returns None after."""

    def test_delete_existing(self, store):
        mem = store.add("to be deleted")
        assert store.get(mem.id) is not None
        ok = store.delete(mem.id)
        assert ok is True
        assert store.get(mem.id) is None


# ---------------------------------------------------------------------------
# 6. test_delete_unknown_id_returns_false
# ---------------------------------------------------------------------------
class TestDeleteUnknownId:
    """delete() should return False for a non-existent id."""

    def test_delete_missing(self, store):
        ok = store.delete("nonexistent")
        assert ok is False


# ---------------------------------------------------------------------------
# 7. test_clear_removes_all
# ---------------------------------------------------------------------------
class TestClearRemovesAll:
    """clear() should remove all memories and return the count."""

    def test_clear(self, store):
        store.add("one")
        store.add("two")
        store.add("three")
        n = store.clear()
        assert n == 3
        assert store.list() == []

    def test_clear_empty_store(self, store):
        n = store.clear()
        assert n == 0


# ---------------------------------------------------------------------------
# 8. test_touch_updates_last_used
# ---------------------------------------------------------------------------
class TestTouchUpdatesLastUsed:
    """touch() should bump last_used and increment use_count."""

    def test_touch(self, store):
        mem = store.add("touchable")
        original_last_used = mem.last_used
        time.sleep(0.02)
        store.touch(mem.id)
        updated = store.get(mem.id)
        assert updated is not None
        assert updated.last_used > original_last_used
        assert updated.use_count == 1

    def test_touch_multiple_times(self, store):
        mem = store.add("multi-touch")
        store.touch(mem.id)
        store.touch(mem.id)
        store.touch(mem.id)
        updated = store.get(mem.id)
        assert updated.use_count == 3


# ---------------------------------------------------------------------------
# 9. test_format_for_prompt_empty
# ---------------------------------------------------------------------------
class TestFormatForPromptEmpty:
    """format_for_prompt() returns empty string for empty list."""

    def test_empty(self, store):
        result = store.format_for_prompt([])
        assert result == ""


# ---------------------------------------------------------------------------
# 10. test_format_for_prompt_with_memories
# ---------------------------------------------------------------------------
class TestFormatForPromptWithMemories:
    """format_for_prompt() returns formatted block with header."""

    def test_with_memories(self, store):
        m1 = store.add("Use pytest for tests")
        m2 = store.add("Always validate input")
        result = store.format_for_prompt([m1, m2])
        assert "## Agent Memory" in result
        assert "- Use pytest for tests" in result
        assert "- Always validate input" in result


# ---------------------------------------------------------------------------
# 11. test_add_with_tags
# ---------------------------------------------------------------------------
class TestAddWithTags:
    """Tags should be stored and searchable."""

    def test_tags_stored(self, store):
        mem = store.add("deploy steps", tags=["devops", "ci"])
        assert mem.tags == ["devops", "ci"]
        retrieved = store.get(mem.id)
        assert retrieved.tags == ["devops", "ci"]

    def test_search_by_tag(self, store):
        store.add("some task", tags=["deployment"])
        store.add("unrelated task")
        results = store.search("deployment")
        assert len(results) == 1
        assert results[0].tags == ["deployment"]


# ---------------------------------------------------------------------------
# 12. test_to_dict_and_from_dict
# ---------------------------------------------------------------------------
class TestSerialization:
    """to_dict() and from_dict() should round-trip correctly."""

    def test_round_trip(self, store):
        from lidco.memory.agent_memory import AgentMemory

        mem = store.add("round-trip test", tags=["test"])
        d = mem.to_dict()
        assert isinstance(d, dict)
        assert d["content"] == "round-trip test"
        assert d["tags"] == ["test"]

        restored = AgentMemory.from_dict(d)
        assert restored.id == mem.id
        assert restored.content == mem.content
        assert restored.tags == mem.tags


# ---------------------------------------------------------------------------
# 13. test_format_for_prompt_with_tags
# ---------------------------------------------------------------------------
class TestFormatForPromptTags:
    """format_for_prompt() includes tag annotations."""

    def test_tags_in_prompt(self, store):
        mem = store.add("Use Docker", tags=["devops", "docker"])
        result = store.format_for_prompt([mem])
        assert "[devops, docker]" in result


# ---------------------------------------------------------------------------
# 14. test_memory_handler_list_empty
# ---------------------------------------------------------------------------
class TestMemoryHandlerListEmpty:
    """/memory list on empty store returns 'No memories stored.'"""

    def test_handler_list_empty(self, tmp_path):
        from lidco.cli.commands.session import _memory_handler_factory

        handler = _memory_handler_factory(tmp_path / "mem.db")
        result = asyncio.run(handler("list"))
        assert "No memories" in result

    def test_handler_default_is_list(self, tmp_path):
        from lidco.cli.commands.session import _memory_handler_factory

        handler = _memory_handler_factory(tmp_path / "mem.db")
        result = asyncio.run(handler(""))
        assert "No memories" in result


# ---------------------------------------------------------------------------
# 15. test_memory_handler_add_and_search
# ---------------------------------------------------------------------------
class TestMemoryHandlerAddAndSearch:
    """/memory add and /memory search work end-to-end."""

    def test_add_then_search(self, tmp_path):
        from lidco.cli.commands.session import _memory_handler_factory

        handler = _memory_handler_factory(tmp_path / "mem.db")
        add_result = asyncio.run(handler("add Always use type hints"))
        assert "saved" in add_result.lower() or "Memory saved" in add_result

        search_result = asyncio.run(handler("search type hints"))
        assert "type hints" in search_result.lower()

    def test_add_empty_returns_usage(self, tmp_path):
        from lidco.cli.commands.session import _memory_handler_factory

        handler = _memory_handler_factory(tmp_path / "mem.db")
        result = asyncio.run(handler("add"))
        assert "Usage" in result

    def test_delete_via_handler(self, tmp_path):
        from lidco.cli.commands.session import _memory_handler_factory

        handler = _memory_handler_factory(tmp_path / "mem.db")
        add_result = asyncio.run(handler("add deleteme"))
        # Extract id from "Memory saved: [<id>] ..."
        mem_id = add_result.split("[")[1].split("]")[0]
        del_result = asyncio.run(handler(f"delete {mem_id}"))
        assert "Deleted" in del_result

    def test_clear_via_handler(self, tmp_path):
        from lidco.cli.commands.session import _memory_handler_factory

        handler = _memory_handler_factory(tmp_path / "mem.db")
        asyncio.run(handler("add one"))
        asyncio.run(handler("add two"))
        result = asyncio.run(handler("clear"))
        assert "Cleared 2" in result

    def test_unknown_subcommand(self, tmp_path):
        from lidco.cli.commands.session import _memory_handler_factory

        handler = _memory_handler_factory(tmp_path / "mem.db")
        result = asyncio.run(handler("badcmd"))
        assert "Usage" in result

    def test_search_empty_returns_usage(self, tmp_path):
        from lidco.cli.commands.session import _memory_handler_factory

        handler = _memory_handler_factory(tmp_path / "mem.db")
        result = asyncio.run(handler("search"))
        assert "Usage" in result

    def test_delete_empty_returns_usage(self, tmp_path):
        from lidco.cli.commands.session import _memory_handler_factory

        handler = _memory_handler_factory(tmp_path / "mem.db")
        result = asyncio.run(handler("delete"))
        assert "Usage" in result
