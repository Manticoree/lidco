"""Tests for src/lidco/cli/commands/q103_cmds.py."""
import asyncio
import pytest


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load_handlers():
    import lidco.cli.commands.q103_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg


class TestEventStoreCommand:
    def test_append_and_load(self):
        reg = _load_handlers()
        handler = reg.commands["event-store"].handler
        _run(handler("append agg1 OrderPlaced"))
        result = _run(handler("load agg1"))
        assert "OrderPlaced" in result

    def test_count(self):
        reg = _load_handlers()
        handler = reg.commands["event-store"].handler
        _run(handler("append agg1 OrderPlaced"))
        result = _run(handler("count"))
        assert "1" in result

    def test_list(self):
        reg = _load_handlers()
        handler = reg.commands["event-store"].handler
        _run(handler("append agg1 OrderPlaced"))
        result = _run(handler("list"))
        assert "agg1" in result

    def test_clear(self):
        reg = _load_handlers()
        handler = reg.commands["event-store"].handler
        _run(handler("append agg1 OrderPlaced"))
        result = _run(handler("clear"))
        assert "cleared" in result.lower()

    def test_load_empty(self):
        reg = _load_handlers()
        handler = reg.commands["event-store"].handler
        result = _run(handler("load unknown_agg"))
        assert "No events" in result or "no events" in result.lower()

    def test_version(self):
        reg = _load_handlers()
        handler = reg.commands["event-store"].handler
        _run(handler("append agg1 OrderPlaced"))
        result = _run(handler("version agg1"))
        assert "1" in result

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["event-store"].handler
        result = _run(handler(""))
        assert "Usage" in result

    def test_unknown_subcommand(self):
        reg = _load_handlers()
        handler = reg.commands["event-store"].handler
        result = _run(handler("badcmd"))
        assert "Unknown" in result


class TestCQRSCommand:
    def test_register_and_dispatch(self):
        reg = _load_handlers()
        handler = reg.commands["cqrs"].handler
        _run(handler("register-cmd CreateUser"))
        result = _run(handler("dispatch-cmd CreateUser"))
        assert "success" in result.lower() or "handled" in result

    def test_list_cmds_empty(self):
        reg = _load_handlers()
        handler = reg.commands["cqrs"].handler
        result = _run(handler("list-cmds"))
        assert "none" in result.lower() or len(result.strip()) == 0 or "(" in result

    def test_list_cmds_with_item(self):
        reg = _load_handlers()
        handler = reg.commands["cqrs"].handler
        _run(handler("register-cmd SomeCmd"))
        result = _run(handler("list-cmds"))
        assert "SomeCmd" in result

    def test_list_queries_empty(self):
        reg = _load_handlers()
        handler = reg.commands["cqrs"].handler
        result = _run(handler("list-queries"))
        assert result is not None

    def test_register_query(self):
        reg = _load_handlers()
        handler = reg.commands["cqrs"].handler
        result = _run(handler("register-query GetUser"))
        assert "GetUser" in result or "registered" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["cqrs"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestSagaCommand:
    def test_add_step(self):
        reg = _load_handlers()
        handler = reg.commands["saga"].handler
        result = _run(handler("add-step reserve"))
        assert "reserve" in result

    def test_execute(self):
        reg = _load_handlers()
        handler = reg.commands["saga"].handler
        _run(handler("add-step s1"))
        result = _run(handler("execute"))
        assert "status" in result.lower() or "completed" in result.lower()

    def test_steps(self):
        reg = _load_handlers()
        handler = reg.commands["saga"].handler
        _run(handler("add-step alpha"))
        result = _run(handler("steps"))
        assert "alpha" in result

    def test_steps_empty(self):
        reg = _load_handlers()
        handler = reg.commands["saga"].handler
        result = _run(handler("steps"))
        assert "no steps" in result.lower() or "(none)" in result.lower()

    def test_clear(self):
        reg = _load_handlers()
        handler = reg.commands["saga"].handler
        _run(handler("add-step s1"))
        result = _run(handler("clear"))
        assert "cleared" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["saga"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestAggregateCommand:
    def test_create(self):
        reg = _load_handlers()
        handler = reg.commands["aggregate"].handler
        result = _run(handler("create order-1"))
        assert "order-1" in result

    def test_apply_event(self):
        reg = _load_handlers()
        handler = reg.commands["aggregate"].handler
        _run(handler("create order-1"))
        result = _run(handler("apply order-1 OrderPlaced"))
        assert "OrderPlaced" in result or "Applied" in result

    def test_version(self):
        reg = _load_handlers()
        handler = reg.commands["aggregate"].handler
        _run(handler("create order-1"))
        _run(handler("apply order-1 OrderPlaced"))
        result = _run(handler("version order-1"))
        assert "1" in result

    def test_history(self):
        reg = _load_handlers()
        handler = reg.commands["aggregate"].handler
        _run(handler("create order-1"))
        _run(handler("apply order-1 OrderPlaced"))
        result = _run(handler("history order-1"))
        assert "OrderPlaced" in result

    def test_apply_unknown_aggregate(self):
        reg = _load_handlers()
        handler = reg.commands["aggregate"].handler
        result = _run(handler("apply nonexistent OrderPlaced"))
        assert "not found" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["aggregate"].handler
        result = _run(handler(""))
        assert "Usage" in result
