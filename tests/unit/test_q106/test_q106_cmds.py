"""Tests for src/lidco/cli/commands/q106_cmds.py."""
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
    import lidco.cli.commands.q106_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg


class TestBuilderCommand:
    def test_demo(self):
        reg = _load_handlers()
        handler = reg.commands["builder"].handler
        result = _run(handler("demo"))
        assert "GET" in result or "get" in result.lower()

    def test_get_and_build(self):
        reg = _load_handlers()
        handler = reg.commands["builder"].handler
        _run(handler("get https://api.example.com"))
        result = _run(handler("build"))
        assert "GET" in result or "https://api.example.com" in result

    def test_post(self):
        reg = _load_handlers()
        handler = reg.commands["builder"].handler
        result = _run(handler("post https://x.com"))
        assert "POST" in result

    def test_header(self):
        reg = _load_handlers()
        handler = reg.commands["builder"].handler
        result = _run(handler("header Content-Type application/json"))
        assert "Content-Type" in result

    def test_timeout(self):
        reg = _load_handlers()
        handler = reg.commands["builder"].handler
        result = _run(handler("timeout 5.0"))
        assert "5" in result

    def test_build_error(self):
        reg = _load_handlers()
        handler = reg.commands["builder"].handler
        _run(handler("reset"))
        result = _run(handler("build"))
        assert "Error" in result

    def test_reset(self):
        reg = _load_handlers()
        handler = reg.commands["builder"].handler
        result = _run(handler("reset"))
        assert "reset" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["builder"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestStrategyCommand:
    def test_sort_asc(self):
        reg = _load_handlers()
        handler = reg.commands["strategy"].handler
        result = _run(handler("sort asc c b a"))
        assert "a" in result

    def test_sort_desc(self):
        reg = _load_handlers()
        handler = reg.commands["strategy"].handler
        result = _run(handler("sort desc a b c"))
        assert "c" in result.split("]")[0] if "]" in result else "c" in result

    def test_compress_rle(self):
        reg = _load_handlers()
        handler = reg.commands["strategy"].handler
        result = _run(handler("compress rle aaabbbcc"))
        assert "3a" in result or "3" in result

    def test_compress_none(self):
        reg = _load_handlers()
        handler = reg.commands["strategy"].handler
        result = _run(handler("compress none hello"))
        assert "hello" in result

    def test_demo(self):
        reg = _load_handlers()
        handler = reg.commands["strategy"].handler
        result = _run(handler("demo"))
        assert "asc" in result.lower() or "desc" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["strategy"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestTemplateCommand:
    def test_text(self):
        reg = _load_handlers()
        handler = reg.commands["template"].handler
        result = _run(handler("text Hello World"))
        assert "hello world" in result.lower() or "hello" in result

    def test_numbers(self):
        reg = _load_handlers()
        handler = reg.commands["template"].handler
        result = _run(handler("numbers 1 -2 3"))
        assert "1" in result
        assert "3" in result

    def test_report(self):
        reg = _load_handlers()
        handler = reg.commands["template"].handler
        result = _run(handler("report My Report"))
        assert "My Report" in result

    def test_demo(self):
        reg = _load_handlers()
        handler = reg.commands["template"].handler
        result = _run(handler("demo"))
        assert "text" in result.lower() or "numbers" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["template"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestDecoratorPatternCommand:
    def test_demo(self):
        reg = _load_handlers()
        handler = reg.commands["decorator-pattern"].handler
        result = _run(handler("demo"))
        assert "HELLO" in result or "hello" in result.lower()

    def test_wrap_upper(self):
        reg = _load_handlers()
        handler = reg.commands["decorator-pattern"].handler
        result = _run(handler("wrap upper hello"))
        assert "HELLO" in result

    def test_wrap_prefix(self):
        reg = _load_handlers()
        handler = reg.commands["decorator-pattern"].handler
        result = _run(handler("wrap prefix:>>> hello"))
        assert ">>>" in result

    def test_wrap_cache(self):
        reg = _load_handlers()
        handler = reg.commands["decorator-pattern"].handler
        result = _run(handler("cache hello"))
        assert "hello" in result

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["decorator-pattern"].handler
        result = _run(handler(""))
        assert "Usage" in result
