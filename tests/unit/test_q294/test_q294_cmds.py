"""Tests for Q294 CLI commands."""
import asyncio
from unittest.mock import MagicMock

import pytest


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


class TestRegisterQ294:
    def test_all_commands_registered(self):
        from lidco.cli.commands.q294_cmds import register_q294_commands
        r = _make_registry()
        register_q294_commands(r)
        assert "notion" in r._handlers
        assert "notion-sync" in r._handlers
        assert "notion-kb" in r._handlers
        assert "notion-meeting" in r._handlers


class TestNotionCommand:
    def _register(self):
        from lidco.cli.commands.q294_cmds import register_q294_commands
        r = _make_registry()
        register_q294_commands(r)
        return _get(r, "notion")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_create_page(self):
        handler = self._register()
        result = asyncio.run(handler('create "Test Page" "Some content"'))
        assert "created" in result.lower()

    def test_create_empty_title_error(self):
        handler = self._register()
        result = asyncio.run(handler('create " "'))
        assert "Error" in result

    def test_search_no_results(self):
        handler = self._register()
        result = asyncio.run(handler("search nonexistent"))
        assert "No pages" in result

    def test_delete_nonexistent(self):
        handler = self._register()
        result = asyncio.run(handler("delete fake_id"))
        assert "not found" in result.lower()

    def test_get_nonexistent(self):
        handler = self._register()
        result = asyncio.run(handler("get fake_id"))
        assert "not found" in result.lower()

    def test_databases_empty(self):
        handler = self._register()
        result = asyncio.run(handler("databases"))
        assert "No databases" in result

    def test_unknown_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("foobar"))
        assert "Unknown" in result


class TestNotionSyncCommand:
    def _register(self):
        from lidco.cli.commands.q294_cmds import register_q294_commands
        r = _make_registry()
        register_q294_commands(r)
        return _get(r, "notion-sync")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_file_not_found(self):
        handler = self._register()
        result = asyncio.run(handler("file /nonexistent/file.md"))
        assert "Error" in result

    def test_status_never_synced(self):
        handler = self._register()
        result = asyncio.run(handler("status /some/path.md"))
        assert "Never synced" in result

    def test_unknown_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("xyz"))
        assert "Unknown" in result


class TestNotionKBCommand:
    def _register(self):
        from lidco.cli.commands.q294_cmds import register_q294_commands
        r = _make_registry()
        register_q294_commands(r)
        return _get(r, "notion-kb")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_add_and_query(self):
        handler = self._register()
        asyncio.run(handler('add "Python Guide" "Learn python programming"'))
        result = asyncio.run(handler("query python"))
        assert "Python Guide" in result

    def test_size_after_add(self):
        handler = self._register()
        asyncio.run(handler('add "Doc" "content"'))
        result = asyncio.run(handler("size"))
        assert "1" in result

    def test_query_no_match(self):
        handler = self._register()
        result = asyncio.run(handler("query zzzzz"))
        assert "No matching" in result

    def test_context_empty(self):
        handler = self._register()
        result = asyncio.run(handler("context anything"))
        assert "No relevant" in result

    def test_unknown_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("xyz"))
        assert "Unknown" in result

    def test_add_missing_args(self):
        handler = self._register()
        result = asyncio.run(handler("add"))
        assert "Error" in result


class TestNotionMeetingCommand:
    def _register(self):
        from lidco.cli.commands.q294_cmds import register_q294_commands
        r = _make_registry()
        register_q294_commands(r)
        return _get(r, "notion-meeting")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_create_meeting(self):
        handler = self._register()
        result = asyncio.run(handler('create "Standup" "Alice,Bob"'))
        assert "created" in result.lower()

    def test_list_empty(self):
        handler = self._register()
        result = asyncio.run(handler("list"))
        assert "No meetings" in result

    def test_notes_nonexistent(self):
        handler = self._register()
        result = asyncio.run(handler('notes bad_id "some text"'))
        assert "not found" in result.lower()

    def test_actions_nonexistent(self):
        handler = self._register()
        result = asyncio.run(handler("actions bad_id"))
        assert "not found" in result.lower()

    def test_assign_nonexistent(self):
        handler = self._register()
        result = asyncio.run(handler("assign bad_id item person"))
        assert "not found" in result.lower()

    def test_unknown_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("xyz"))
        assert "Unknown" in result

    def test_create_missing_title(self):
        handler = self._register()
        result = asyncio.run(handler("create"))
        assert "Error" in result
