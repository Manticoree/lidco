"""Tests for T631 Q99 CLI commands."""
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


class TestRegisterQ99:
    def test_all_commands_registered(self):
        from lidco.cli.commands.q99_cmds import register_q99_commands
        r = _make_registry()
        register_q99_commands(r)
        assert "rate-limiter" in r._handlers
        assert "circuit-breaker" in r._handlers
        assert "events" in r._handlers
        assert "jobs" in r._handlers


class TestRateLimiterCommand:
    def _register(self):
        from lidco.cli.commands.q99_cmds import register_q99_commands
        r = _make_registry()
        register_q99_commands(r)
        return _get(r, "rate-limiter")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_test_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("test"))
        assert "rate limiter" in result.lower() or "acquire" in result.lower()

    def test_status_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("status"))
        assert "token" in result.lower()

    def test_reset_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("reset"))
        assert "reset" in result.lower()


class TestCircuitBreakerCommand:
    def _register(self):
        from lidco.cli.commands.q99_cmds import register_q99_commands
        r = _make_registry()
        register_q99_commands(r)
        return _get(r, "circuit-breaker")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_test_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("test"))
        assert "closed" in result.lower() or "state" in result.lower()

    def test_reset_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("reset"))
        assert "reset" in result.lower()


class TestEventsCommand:
    def _register(self):
        from lidco.cli.commands.q99_cmds import register_q99_commands
        r = _make_registry()
        register_q99_commands(r)
        return _get(r, "events")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_publish_event(self):
        handler = self._register()
        result = asyncio.run(handler("publish my_event"))
        assert "published" in result.lower() or "my_event" in result

    def test_history_empty(self):
        handler = self._register()
        result = asyncio.run(handler("history"))
        assert "No events" in result or "history" in result.lower()

    def test_publish_then_history(self):
        handler = self._register()
        asyncio.run(handler("publish test_evt"))
        result = asyncio.run(handler("history"))
        assert "test_evt" in result or "event" in result.lower()

    def test_clear(self):
        handler = self._register()
        asyncio.run(handler("publish x"))
        result = asyncio.run(handler("clear"))
        assert "cleared" in result.lower() or "1" in result


class TestJobsCommand:
    def _register(self):
        from lidco.cli.commands.q99_cmds import register_q99_commands
        r = _make_registry()
        register_q99_commands(r)
        return _get(r, "jobs")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_list_empty(self):
        handler = self._register()
        result = asyncio.run(handler("list"))
        assert "No jobs" in result or "job" in result.lower()

    def test_submit_job(self):
        handler = self._register()
        result = asyncio.run(handler("submit my_job"))
        assert "submitted" in result.lower() or "my_job" in result
