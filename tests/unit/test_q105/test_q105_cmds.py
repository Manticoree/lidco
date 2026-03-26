"""Tests for src/lidco/cli/commands/q105_cmds.py."""
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
    import lidco.cli.commands.q105_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg


class TestValueObjectCommand:
    def test_demo(self):
        reg = _load_handlers()
        handler = reg.commands["value-object"].handler
        result = _run(handler("demo"))
        assert "Money" in result or "money" in result.lower()

    def test_money(self):
        reg = _load_handlers()
        handler = reg.commands["value-object"].handler
        result = _run(handler("money 10.0 USD"))
        assert "10.0" in result or "USD" in result

    def test_email_valid(self):
        reg = _load_handlers()
        handler = reg.commands["value-object"].handler
        result = _run(handler("email user@example.com"))
        assert "example.com" in result

    def test_email_invalid(self):
        reg = _load_handlers()
        handler = reg.commands["value-object"].handler
        result = _run(handler("email notanemail"))
        assert "Invalid" in result or "invalid" in result.lower()

    def test_phone_valid(self):
        reg = _load_handlers()
        handler = reg.commands["value-object"].handler
        result = _run(handler("phone 1234567890"))
        assert "1234567890" in result

    def test_phone_invalid(self):
        reg = _load_handlers()
        handler = reg.commands["value-object"].handler
        result = _run(handler("phone 123"))
        assert "Invalid" in result or "invalid" in result.lower()

    def test_unknown_subcommand(self):
        reg = _load_handlers()
        handler = reg.commands["value-object"].handler
        result = _run(handler("badcmd"))
        assert "Unknown" in result

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["value-object"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestEntityCommand:
    def test_create(self):
        reg = _load_handlers()
        handler = reg.commands["entity"].handler
        result = _run(handler("create"))
        assert "Created" in result

    def test_create_with_id(self):
        reg = _load_handlers()
        handler = reg.commands["entity"].handler
        result = _run(handler("create my-entity"))
        assert "my-entity" in result

    def test_touch(self):
        reg = _load_handlers()
        handler = reg.commands["entity"].handler
        _run(handler("create my-id"))
        result = _run(handler("touch my-id"))
        assert "my-id" in result or "Touched" in result

    def test_delete(self):
        reg = _load_handlers()
        handler = reg.commands["entity"].handler
        _run(handler("create my-id"))
        result = _run(handler("delete my-id"))
        assert "deleted" in result.lower() or "True" in result

    def test_restore(self):
        reg = _load_handlers()
        handler = reg.commands["entity"].handler
        _run(handler("create my-id"))
        _run(handler("delete my-id"))
        result = _run(handler("restore my-id"))
        assert "False" in result or "restored" in result.lower()

    def test_list(self):
        reg = _load_handlers()
        handler = reg.commands["entity"].handler
        _run(handler("create e1"))
        result = _run(handler("list"))
        assert "e1" in result

    def test_info(self):
        reg = _load_handlers()
        handler = reg.commands["entity"].handler
        _run(handler("create my-id"))
        result = _run(handler("info my-id"))
        assert "my-id" in result

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["entity"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestDomainEventsCommand:
    def test_publish(self):
        reg = _load_handlers()
        handler = reg.commands["domain-events"].handler
        result = _run(handler("publish OrderPlaced"))
        assert "Published" in result or "OrderPlaced" in result

    def test_subscribe(self):
        reg = _load_handlers()
        handler = reg.commands["domain-events"].handler
        result = _run(handler("subscribe OrderPlaced"))
        assert "Subscribed" in result

    def test_history(self):
        reg = _load_handlers()
        handler = reg.commands["domain-events"].handler
        _run(handler("publish OrderPlaced"))
        result = _run(handler("history"))
        assert "OrderPlaced" in result

    def test_history_empty(self):
        reg = _load_handlers()
        handler = reg.commands["domain-events"].handler
        result = _run(handler("history"))
        assert "no events" in result.lower()

    def test_clear(self):
        reg = _load_handlers()
        handler = reg.commands["domain-events"].handler
        _run(handler("publish OrderPlaced"))
        result = _run(handler("clear"))
        assert "Cleared" in result

    def test_count(self):
        reg = _load_handlers()
        handler = reg.commands["domain-events"].handler
        _run(handler("publish OrderPlaced"))
        result = _run(handler("count"))
        assert "1" in result

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["domain-events"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestMoneyCommand:
    def test_add(self):
        reg = _load_handlers()
        handler = reg.commands["money"].handler
        result = _run(handler("add 10.0 USD 5.0 USD"))
        assert "15" in result or "15.0" in result

    def test_subtract(self):
        reg = _load_handlers()
        handler = reg.commands["money"].handler
        result = _run(handler("subtract 10.0 USD 3.0 USD"))
        assert "7" in result

    def test_multiply(self):
        reg = _load_handlers()
        handler = reg.commands["money"].handler
        result = _run(handler("multiply 10.0 USD 2.0"))
        assert "20" in result

    def test_add_different_currency(self):
        reg = _load_handlers()
        handler = reg.commands["money"].handler
        result = _run(handler("add 10.0 USD 5.0 EUR"))
        assert "Error" in result

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["money"].handler
        result = _run(handler(""))
        assert "Usage" in result
