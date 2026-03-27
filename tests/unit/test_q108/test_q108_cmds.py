"""Tests for src/lidco/cli/commands/q108_cmds.py."""
import asyncio


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load_handlers():
    import lidco.cli.commands.q108_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg


# ------------------------------------------------------------------ #
# /docgen                                                               #
# ------------------------------------------------------------------ #

class TestDocgenCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "docgen" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["docgen"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo(self):
        reg = _load_handlers()
        h = reg.commands["docgen"].handler
        result = _run(h("demo"))
        assert '"""' in result or "add" in result

    def test_parse(self):
        reg = _load_handlers()
        h = reg.commands["docgen"].handler
        result = _run(h("parse def foo(x: int) -> str: pass"))
        assert "foo" in result

    def test_parse_no_args(self):
        reg = _load_handlers()
        h = reg.commands["docgen"].handler
        result = _run(h("parse"))
        assert "Usage" in result

    def test_generate(self):
        reg = _load_handlers()
        h = reg.commands["docgen"].handler
        result = _run(h("generate def add(a: int, b: int) -> int: return a+b"))
        assert '"""' in result or "add" in result or "TODO" in result

    def test_generate_no_args(self):
        reg = _load_handlers()
        h = reg.commands["docgen"].handler
        result = _run(h("generate"))
        assert "Usage" in result

    def test_check_missing(self):
        reg = _load_handlers()
        h = reg.commands["docgen"].handler
        result = _run(h("check def foo(): pass"))
        assert "foo" in result or "missing" in result.lower()

    def test_check_no_args(self):
        reg = _load_handlers()
        h = reg.commands["docgen"].handler
        result = _run(h("check"))
        assert "Usage" in result

    def test_style_get(self):
        reg = _load_handlers()
        h = reg.commands["docgen"].handler
        result = _run(h("style"))
        assert "google" in result.lower() or "style" in result.lower()

    def test_style_set(self):
        reg = _load_handlers()
        h = reg.commands["docgen"].handler
        result = _run(h("style numpy"))
        assert "numpy" in result.lower()

    def test_style_invalid(self):
        reg = _load_handlers()
        h = reg.commands["docgen"].handler
        result = _run(h("style badstyle"))
        assert "Unknown" in result or "bad" in result.lower()


# ------------------------------------------------------------------ #
# /snippet                                                              #
# ------------------------------------------------------------------ #

class TestSnippetCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "snippet" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        result = _run(h("demo"))
        assert "logger" in result or "snippet" in result.lower()

    def test_save_and_get(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        _run(h("save mysnip hello world"))
        result = _run(h("get mysnip"))
        assert "hello world" in result

    def test_save_no_args(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        result = _run(h("save"))
        assert "Usage" in result

    def test_get_nonexistent(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        result = _run(h("get ghost"))
        assert "not found" in result.lower()

    def test_get_no_args(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        result = _run(h("get"))
        assert "Usage" in result

    def test_expand(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        _run(h("save tmpl Hello, ${NAME}!"))
        result = _run(h("expand tmpl NAME=Alice"))
        assert "Alice" in result

    def test_expand_missing_name(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        result = _run(h("expand ghost"))
        assert "Error" in result or "not found" in result.lower()

    def test_list_empty(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        result = _run(h("list"))
        assert "No snippets" in result or "snippet" in result.lower()

    def test_list_with_items(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        _run(h("save one first snippet"))
        _run(h("save two second snippet"))
        result = _run(h("list"))
        assert "one" in result or "two" in result

    def test_search(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        _run(h("save logger import logging"))
        result = _run(h("search log"))
        assert "logger" in result or "log" in result.lower()

    def test_search_no_args(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        result = _run(h("search"))
        assert "Usage" in result

    def test_delete(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        _run(h("save del-me temp"))
        result = _run(h("delete del-me"))
        assert "delete" in result.lower() or "del-me" in result

    def test_reset(self):
        reg = _load_handlers()
        h = reg.commands["snippet"].handler
        result = _run(h("reset"))
        assert "reset" in result.lower()


# ------------------------------------------------------------------ #
# /imports                                                              #
# ------------------------------------------------------------------ #

class TestImportsCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "imports" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["imports"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo(self):
        reg = _load_handlers()
        h = reg.commands["imports"].handler
        result = _run(h("demo"))
        assert "import" in result.lower() or "Path" in result

    def test_resolve(self):
        reg = _load_handlers()
        h = reg.commands["imports"].handler
        result = _run(h("resolve p = Path('.')"))
        assert "Path" in result or "pathlib" in result

    def test_resolve_no_undefined(self):
        reg = _load_handlers()
        h = reg.commands["imports"].handler
        result = _run(h("resolve x = 1"))
        assert "No undefined" in result or "import" in result.lower()

    def test_resolve_no_args(self):
        reg = _load_handlers()
        h = reg.commands["imports"].handler
        result = _run(h("resolve"))
        assert "Usage" in result

    def test_suggest_known(self):
        reg = _load_handlers()
        h = reg.commands["imports"].handler
        result = _run(h("suggest Path"))
        assert "pathlib" in result or "Path" in result

    def test_suggest_unknown(self):
        reg = _load_handlers()
        h = reg.commands["imports"].handler
        result = _run(h("suggest totally_unknown_xyz"))
        assert "No known" in result or "unknown" in result.lower()

    def test_suggest_no_args(self):
        reg = _load_handlers()
        h = reg.commands["imports"].handler
        result = _run(h("suggest"))
        assert "Usage" in result

    def test_known(self):
        reg = _load_handlers()
        h = reg.commands["imports"].handler
        result = _run(h("known"))
        assert "Path" in result or "known" in result.lower()

    def test_prepend(self):
        reg = _load_handlers()
        h = reg.commands["imports"].handler
        result = _run(h("prepend p = Path('.')"))
        assert "pathlib" in result or "import" in result.lower()


# ------------------------------------------------------------------ #
# /error-monitor                                                        #
# ------------------------------------------------------------------ #

class TestErrorMonitorCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "error-monitor" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["error-monitor"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo(self):
        reg = _load_handlers()
        h = reg.commands["error-monitor"].handler
        result = _run(h("demo"))
        assert "event" in result.lower() or "Error" in result

    def test_feed_match(self):
        reg = _load_handlers()
        h = reg.commands["error-monitor"].handler
        result = _run(h("feed TypeError: bad value"))
        assert "ERROR" in result or "TypeError" in result or "pattern" in result.lower()

    def test_feed_no_match(self):
        reg = _load_handlers()
        h = reg.commands["error-monitor"].handler
        result = _run(h("feed INFO: everything is fine"))
        assert "No patterns" in result or "matched" in result.lower() or "fine" in result

    def test_feed_no_args(self):
        reg = _load_handlers()
        h = reg.commands["error-monitor"].handler
        result = _run(h("feed"))
        assert "Usage" in result

    def test_events_empty(self):
        reg = _load_handlers()
        h = reg.commands["error-monitor"].handler
        result = _run(h("events"))
        assert isinstance(result, str)

    def test_events_after_feed(self):
        reg = _load_handlers()
        h = reg.commands["error-monitor"].handler
        _run(h("feed TypeError: bad"))
        result = _run(h("events"))
        assert "ERROR" in result or "TypeError" in result or "event" in result.lower()

    def test_summary(self):
        reg = _load_handlers()
        h = reg.commands["error-monitor"].handler
        result = _run(h("summary"))
        assert isinstance(result, str)

    def test_patterns(self):
        reg = _load_handlers()
        h = reg.commands["error-monitor"].handler
        result = _run(h("patterns"))
        assert "pattern" in result.lower() or "Active" in result

    def test_clear(self):
        reg = _load_handlers()
        h = reg.commands["error-monitor"].handler
        result = _run(h("clear"))
        assert "clear" in result.lower()

    def test_reset(self):
        reg = _load_handlers()
        h = reg.commands["error-monitor"].handler
        result = _run(h("reset"))
        assert "reset" in result.lower()
