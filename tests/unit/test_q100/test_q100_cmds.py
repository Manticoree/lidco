"""Tests for T636 Q100 CLI commands."""
import asyncio
from unittest.mock import MagicMock, patch

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


class TestRegisterQ100:
    def test_all_commands_registered(self):
        from lidco.cli.commands.q100_cmds import register_q100_commands
        r = _make_registry()
        register_q100_commands(r)
        assert "kv" in r._handlers
        assert "mq" in r._handlers
        assert "state-machine" in r._handlers
        assert "retry" in r._handlers


class TestKVCommand:
    def _register(self):
        from lidco.cli.commands.q100_cmds import register_q100_commands
        r = _make_registry()
        register_q100_commands(r)
        return _get(r, "kv")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_set_and_get(self):
        handler = self._register()
        asyncio.run(handler("set mykey myvalue"))
        result = asyncio.run(handler("get mykey"))
        assert "mykey" in result or "myvalue" in result

    def test_get_missing(self):
        handler = self._register()
        result = asyncio.run(handler("get nonexistent_key"))
        assert "not found" in result.lower()

    def test_list_empty(self):
        handler = self._register()
        result = asyncio.run(handler("list"))
        assert "No keys" in result or "keys" in result.lower()

    def test_list_shows_key(self):
        handler = self._register()
        asyncio.run(handler("set testkey testval"))
        result = asyncio.run(handler("list"))
        assert "testkey" in result

    def test_delete_key(self):
        handler = self._register()
        asyncio.run(handler("set delkey val"))
        result = asyncio.run(handler("delete delkey"))
        assert "deleted" in result.lower() or "delkey" in result

    def test_flush(self):
        handler = self._register()
        result = asyncio.run(handler("flush"))
        assert "flushed" in result.lower()

    def test_clear(self):
        handler = self._register()
        asyncio.run(handler("set k1 v1"))
        result = asyncio.run(handler("clear"))
        assert "cleared" in result.lower() or "1" in result


class TestMQCommand:
    def _register(self):
        from lidco.cli.commands.q100_cmds import register_q100_commands
        r = _make_registry()
        register_q100_commands(r)
        return _get(r, "mq")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_enqueue_returns_id(self):
        handler = self._register()
        result = asyncio.run(handler('enqueue test_topic {"key":"val"}'))
        assert "enqueued" in result.lower() or "test_topic" in result

    def test_topics_empty(self):
        handler = self._register()
        result = asyncio.run(handler("topics"))
        assert "No topics" in result or "topic" in result.lower()

    def test_enqueue_then_topics(self):
        handler = self._register()
        asyncio.run(handler('enqueue my_topic {}'))
        result = asyncio.run(handler("topics"))
        assert "my_topic" in result

    def test_dlq_empty(self):
        handler = self._register()
        result = asyncio.run(handler("dlq"))
        assert "No dead" in result or "dead" in result.lower()


class TestStateMachineCommand:
    def _register(self):
        from lidco.cli.commands.q100_cmds import register_q100_commands
        r = _make_registry()
        register_q100_commands(r)
        return _get(r, "state-machine")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_create(self):
        handler = self._register()
        result = asyncio.run(handler("create idle"))
        assert "created" in result.lower() or "idle" in result

    def test_status_after_create(self):
        handler = self._register()
        asyncio.run(handler("create idle"))
        result = asyncio.run(handler("status"))
        assert "idle" in result

    def test_trigger_then_status(self):
        handler = self._register()
        asyncio.run(handler("create idle"))
        asyncio.run(handler("add-transition idle active --on start"))
        asyncio.run(handler("trigger start"))
        result = asyncio.run(handler("status"))
        assert "active" in result

    def test_history_empty(self):
        handler = self._register()
        asyncio.run(handler("create idle"))
        result = asyncio.run(handler("history"))
        assert "No transitions" in result or "history" in result.lower()


class TestRetryCommand:
    def _register(self):
        from lidco.cli.commands.q100_cmds import register_q100_commands
        r = _make_registry()
        register_q100_commands(r)
        return _get(r, "retry")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_test_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("test --attempts 3"))
        assert "attempt" in result.lower() or "success" in result.lower()

    def test_policy_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("policy --attempts 2 --delay 1.0"))
        assert "policy" in result.lower() or "delay" in result.lower()
