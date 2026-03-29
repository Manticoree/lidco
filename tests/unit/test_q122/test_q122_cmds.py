"""Tests for src/lidco/cli/commands/q122_cmds.py."""
import asyncio


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load():
    import lidco.cli.commands.q122_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg, mod


class TestBudgetCmdRegistered:
    def test_registered(self):
        reg, _ = _load()
        assert "budget" in reg.commands

    def test_no_args_returns_usage(self):
        reg, _ = _load()
        result = _run(reg.commands["budget"].handler(""))
        assert "Usage" in result or "show" in result.lower()


class TestBudgetShow:
    def test_show_empty_messages(self):
        reg, _ = _load()
        result = _run(reg.commands["budget"].handler("show"))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_show_contains_percentage(self):
        reg, _ = _load()
        result = _run(reg.commands["budget"].handler("show"))
        assert "%" in result or "Context" in result or "tokens" in result.lower()

    def test_show_with_messages(self):
        reg, mod = _load()
        mod._state["messages"] = [
            {"role": "system", "content": "You are an assistant."},
            {"role": "user", "content": "Hello!"},
        ]
        result = _run(reg.commands["budget"].handler("show"))
        assert isinstance(result, str)
        assert len(result) > 0


class TestBudgetAllocate:
    def test_allocate_returns_plan(self):
        reg, _ = _load()
        result = _run(reg.commands["budget"].handler("allocate"))
        assert isinstance(result, str)
        assert "Budget" in result or "tokens" in result.lower()

    def test_allocate_shows_slots(self):
        reg, _ = _load()
        result = _run(reg.commands["budget"].handler("allocate"))
        assert "system" in result.lower() or "history" in result.lower()

    def test_allocate_with_custom_budget(self):
        reg, mod = _load()
        mod._state["budget"] = 16384
        result = _run(reg.commands["budget"].handler("allocate"))
        assert "16384" in result


class TestBudgetTrim:
    def test_trim_no_messages(self):
        reg, _ = _load()
        result = _run(reg.commands["budget"].handler("trim"))
        assert "No messages" in result or "state" in result.lower()

    def test_trim_with_messages(self):
        reg, mod = _load()
        mod._state["messages"] = [
            {"role": "user", "content": "msg " * 100},
            {"role": "user", "content": "msg " * 100},
            {"role": "user", "content": "recent"},
        ]
        mod._state["budget"] = 50
        result = _run(reg.commands["budget"].handler("trim"))
        assert isinstance(result, str)

    def test_trim_updates_state_messages(self):
        reg, mod = _load()
        mod._state["messages"] = [
            {"role": "user", "content": "msg " * 50},
        ]
        mod._state["budget"] = 10000  # large enough → no trimming
        _run(reg.commands["budget"].handler("trim"))
        assert "messages" in mod._state

    def test_trim_result_message(self):
        reg, mod = _load()
        mod._state["messages"] = [{"role": "user", "content": "hello"}]
        mod._state["budget"] = 10000
        result = _run(reg.commands["budget"].handler("trim"))
        assert "Trimmed" in result or "message" in result.lower()


class TestBudgetUnknown:
    def test_unknown_sub(self):
        reg, _ = _load()
        result = _run(reg.commands["budget"].handler("unknown"))
        assert "Usage" in result or "show" in result.lower()
