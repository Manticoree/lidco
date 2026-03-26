"""Tests for src/lidco/cli/commands/q104_cmds.py."""
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
    import lidco.cli.commands.q104_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg


class TestRepoCommand:
    def test_save_and_get(self):
        reg = _load_handlers()
        handler = reg.commands["repo"].handler
        _run(handler("save item1 hello"))
        result = _run(handler("get item1"))
        assert "item1" in result or "hello" in result

    def test_get_missing(self):
        reg = _load_handlers()
        handler = reg.commands["repo"].handler
        result = _run(handler("get missing"))
        assert "Not found" in result or "not found" in result.lower()

    def test_delete(self):
        reg = _load_handlers()
        handler = reg.commands["repo"].handler
        _run(handler("save x val"))
        result = _run(handler("delete x"))
        assert "True" in result

    def test_list_empty(self):
        reg = _load_handlers()
        handler = reg.commands["repo"].handler
        result = _run(handler("list"))
        assert "empty" in result.lower()

    def test_list_with_items(self):
        reg = _load_handlers()
        handler = reg.commands["repo"].handler
        _run(handler("save a va"))
        result = _run(handler("list"))
        assert "a" in result

    def test_count(self):
        reg = _load_handlers()
        handler = reg.commands["repo"].handler
        _run(handler("save a va"))
        result = _run(handler("count"))
        assert "1" in result

    def test_clear(self):
        reg = _load_handlers()
        handler = reg.commands["repo"].handler
        _run(handler("save a va"))
        result = _run(handler("clear"))
        assert "cleared" in result.lower()

    def test_exists(self):
        reg = _load_handlers()
        handler = reg.commands["repo"].handler
        _run(handler("save x val"))
        result = _run(handler("exists x"))
        assert "True" in result

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["repo"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestUoWCommand:
    def test_begin(self):
        reg = _load_handlers()
        handler = reg.commands["uow"].handler
        result = _run(handler("begin"))
        assert "started" in result.lower() or "Transaction" in result

    def test_register_new_and_commit(self):
        reg = _load_handlers()
        handler = reg.commands["uow"].handler
        _run(handler("new entity1"))
        result = _run(handler("commit"))
        assert "entity1" in result

    def test_rollback(self):
        reg = _load_handlers()
        handler = reg.commands["uow"].handler
        _run(handler("new entity1"))
        result = _run(handler("rollback"))
        assert "rolled back" in result.lower() or "rollback" in result.lower()

    def test_status(self):
        reg = _load_handlers()
        handler = reg.commands["uow"].handler
        result = _run(handler("status"))
        assert "active" in result.lower() or "pending" in result.lower()

    def test_dirty(self):
        reg = _load_handlers()
        handler = reg.commands["uow"].handler
        result = _run(handler("dirty e1"))
        assert "e1" in result

    def test_removed(self):
        reg = _load_handlers()
        handler = reg.commands["uow"].handler
        result = _run(handler("removed e1"))
        assert "e1" in result

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["uow"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestSpecCommand:
    def test_eval_gt(self):
        reg = _load_handlers()
        handler = reg.commands["spec"].handler
        result = _run(handler("eval gt:10 15"))
        assert "True" in result

    def test_eval_lt(self):
        reg = _load_handlers()
        handler = reg.commands["spec"].handler
        result = _run(handler("eval lt:20 15"))
        assert "True" in result

    def test_eval_eq(self):
        reg = _load_handlers()
        handler = reg.commands["spec"].handler
        result = _run(handler("eval eq:hello hello"))
        assert "True" in result

    def test_eval_nonempty(self):
        reg = _load_handlers()
        handler = reg.commands["spec"].handler
        result = _run(handler("eval nonempty hello"))
        assert "True" in result

    def test_demo(self):
        reg = _load_handlers()
        handler = reg.commands["spec"].handler
        result = _run(handler("demo"))
        assert "AND" in result or "and" in result.lower() or "[" in result

    def test_unknown_rule(self):
        reg = _load_handlers()
        handler = reg.commands["spec"].handler
        result = _run(handler("eval invalid:bad 5"))
        assert "Unknown" in result or "unknown" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["spec"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestDomainServiceCommand:
    def test_register_and_get(self):
        reg = _load_handlers()
        handler = reg.commands["domain-service"].handler
        _run(handler("register pricing"))
        result = _run(handler("get pricing"))
        assert "pricing" in result

    def test_get_missing(self):
        reg = _load_handlers()
        handler = reg.commands["domain-service"].handler
        result = _run(handler("get no_such"))
        assert "Not found" in result or "not found" in result.lower()

    def test_list_empty(self):
        reg = _load_handlers()
        handler = reg.commands["domain-service"].handler
        result = _run(handler("list"))
        assert "(none)" in result

    def test_list_with_items(self):
        reg = _load_handlers()
        handler = reg.commands["domain-service"].handler
        _run(handler("register pricing"))
        result = _run(handler("list"))
        assert "pricing" in result

    def test_unregister(self):
        reg = _load_handlers()
        handler = reg.commands["domain-service"].handler
        _run(handler("register pricing"))
        result = _run(handler("unregister pricing"))
        assert "True" in result

    def test_clear(self):
        reg = _load_handlers()
        handler = reg.commands["domain-service"].handler
        _run(handler("register pricing"))
        result = _run(handler("clear"))
        assert "cleared" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["domain-service"].handler
        result = _run(handler(""))
        assert "Usage" in result
