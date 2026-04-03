"""Tests for Q243 CLI commands."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from lidco.cli.commands.q243_cmds import register_q243_commands


def _make_registry():
    registry = MagicMock()
    registered = {}

    def register_async(name, desc, handler):
        registered[name] = handler

    registry.register_async.side_effect = register_async
    registry._handlers = registered
    return registry


def _get(registry, name):
    return registry._handlers[name]


class TestRegisterQ243:
    def test_all_commands_registered(self):
        r = _make_registry()
        register_q243_commands(r)
        assert "context-segments" in r._handlers
        assert "virtual-memory" in r._handlers
        assert "defrag" in r._handlers
        assert "context-schedule" in r._handlers

    def test_register_count(self):
        r = _make_registry()
        register_q243_commands(r)
        assert len(r._handlers) == 4


class TestContextSegmentsCommand:
    def _handler(self):
        r = _make_registry()
        register_q243_commands(r)
        return _get(r, "context-segments")

    def test_no_args_shows_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        assert "Usage" in result

    def test_list_shows_defaults(self):
        h = self._handler()
        result = asyncio.run(h("list"))
        assert "system" in result
        assert "tools" in result

    def test_create_segment(self):
        h = self._handler()
        result = asyncio.run(h("create test 5000"))
        assert "Created" in result

    def test_create_duplicate(self):
        h = self._handler()
        asyncio.run(h("create dup 100"))
        result = asyncio.run(h("create dup 200"))
        assert "already exists" in result

    def test_add_entry(self):
        h = self._handler()
        result = asyncio.run(h("add system hello world"))
        assert "Added" in result

    def test_resize(self):
        h = self._handler()
        result = asyncio.run(h("resize system 5000"))
        assert "Resized" in result

    def test_stats(self):
        h = self._handler()
        result = asyncio.run(h("stats"))
        assert "Segments" in result

    def test_unknown_subcommand(self):
        h = self._handler()
        result = asyncio.run(h("bogus"))
        assert "Unknown" in result


class TestVirtualMemoryCommand:
    def _handler(self):
        r = _make_registry()
        register_q243_commands(r)
        return _get(r, "virtual-memory")

    def test_no_args_shows_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        assert "Usage" in result

    def test_add_page(self):
        h = self._handler()
        result = asyncio.run(h("add p1 some content"))
        assert "Added" in result

    def test_access_page(self):
        h = self._handler()
        asyncio.run(h("add p1 test content"))
        result = asyncio.run(h("access p1"))
        assert "test content" in result

    def test_access_missing(self):
        h = self._handler()
        result = asyncio.run(h("access nope"))
        assert "not found" in result

    def test_evict(self):
        h = self._handler()
        asyncio.run(h("add p1 content"))
        result = asyncio.run(h("evict"))
        assert "Evicted" in result

    def test_working_set(self):
        h = self._handler()
        asyncio.run(h("add p1 content"))
        result = asyncio.run(h("working-set"))
        assert "p1" in result

    def test_stats(self):
        h = self._handler()
        result = asyncio.run(h("stats"))
        assert "Pages" in result

    def test_unknown_subcommand(self):
        h = self._handler()
        result = asyncio.run(h("bogus"))
        assert "Unknown" in result


class TestDefragCommand:
    def _handler(self):
        r = _make_registry()
        register_q243_commands(r)
        return _get(r, "defrag")

    def test_no_args_shows_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        assert "Usage" in result

    def test_run(self):
        h = self._handler()
        result = asyncio.run(h("run"))
        assert "Defrag complete" in result

    def test_compact(self):
        h = self._handler()
        result = asyncio.run(h("compact system"))
        assert "Compacted" in result

    def test_stats(self):
        h = self._handler()
        result = asyncio.run(h("stats"))
        assert "Defrag runs" in result

    def test_unknown_subcommand(self):
        h = self._handler()
        result = asyncio.run(h("bogus"))
        assert "Unknown" in result


class TestContextScheduleCommand:
    def _handler(self):
        r = _make_registry()
        register_q243_commands(r)
        return _get(r, "context-schedule")

    def test_no_args_shows_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        assert "Usage" in result

    def test_add_entry(self):
        h = self._handler()
        result = asyncio.run(h("add e1 10 code some content here"))
        assert "Added" in result
        assert "e1" in result

    def test_run_schedule(self):
        h = self._handler()
        asyncio.run(h("add e1 10 code some content"))
        result = asyncio.run(h("run 10000"))
        assert "Scheduled" in result

    def test_run_empty(self):
        h = self._handler()
        result = asyncio.run(h("run 10000"))
        assert "No entries" in result

    def test_remove(self):
        h = self._handler()
        asyncio.run(h("add e1 10 code content"))
        result = asyncio.run(h("remove e1"))
        assert "Removed" in result

    def test_remove_missing(self):
        h = self._handler()
        result = asyncio.run(h("remove nope"))
        assert "not found" in result

    def test_stats(self):
        h = self._handler()
        result = asyncio.run(h("stats"))
        assert "Entries" in result

    def test_unknown_subcommand(self):
        h = self._handler()
        result = asyncio.run(h("bogus"))
        assert "Unknown" in result
