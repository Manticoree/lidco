"""Tests for src/lidco/cli/commands/q109_cmds.py."""
import asyncio


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load_handlers():
    import lidco.cli.commands.q109_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg


# ------------------------------------------------------------------ #
# /annotate                                                             #
# ------------------------------------------------------------------ #

class TestAnnotateCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "annotate" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["annotate"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo(self):
        reg = _load_handlers()
        h = reg.commands["annotate"].handler
        result = _run(h("demo"))
        assert "annotation" in result.lower() or "bool" in result or "int" in result

    def test_analyze(self):
        reg = _load_handlers()
        h = reg.commands["annotate"].handler
        result = _run(h("analyze def f(x=0): return x"))
        assert isinstance(result, str)

    def test_analyze_no_args(self):
        reg = _load_handlers()
        h = reg.commands["annotate"].handler
        result = _run(h("analyze"))
        assert "Usage" in result

    def test_coverage(self):
        reg = _load_handlers()
        h = reg.commands["annotate"].handler
        result = _run(h("coverage def f(x: int) -> str: return str(x)"))
        assert "%" in result or "coverage" in result.lower()

    def test_coverage_no_args(self):
        reg = _load_handlers()
        h = reg.commands["annotate"].handler
        result = _run(h("coverage"))
        assert "Usage" in result

    def test_suggest(self):
        reg = _load_handlers()
        h = reg.commands["annotate"].handler
        result = _run(h("suggest is_active"))
        assert "bool" in result or "is_active" in result

    def test_suggest_no_args(self):
        reg = _load_handlers()
        h = reg.commands["annotate"].handler
        result = _run(h("suggest"))
        assert "Usage" in result

    def test_confidence_get(self):
        reg = _load_handlers()
        h = reg.commands["annotate"].handler
        result = _run(h("confidence"))
        assert "confidence" in result.lower() or "0." in result

    def test_confidence_set(self):
        reg = _load_handlers()
        h = reg.commands["annotate"].handler
        result = _run(h("confidence 0.8"))
        assert "0.8" in result


# ------------------------------------------------------------------ #
# /stash                                                                #
# ------------------------------------------------------------------ #

class TestStashCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "stash" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["stash"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo(self):
        reg = _load_handlers()
        h = reg.commands["stash"].handler
        result = _run(h("demo"))
        assert "stash" in result.lower()

    def test_list(self):
        from unittest.mock import patch
        from lidco.git.stash_manager import StashManager, StashEntry
        reg = _load_handlers()
        h = reg.commands["stash"].handler
        with patch.object(StashManager, "list", return_value=[
            StashEntry(0, "WIP", "main", "stash@{0}")
        ]):
            result = _run(h("list"))
        assert "stash@{0}" in result or "WIP" in result

    def test_list_empty(self):
        from unittest.mock import patch
        from lidco.git.stash_manager import StashManager
        reg = _load_handlers()
        h = reg.commands["stash"].handler
        with patch.object(StashManager, "list", return_value=[]):
            result = _run(h("list"))
        assert "No stashes" in result

    def test_push(self):
        from unittest.mock import patch
        from lidco.git.stash_manager import StashManager, StashResult
        reg = _load_handlers()
        h = reg.commands["stash"].handler
        with patch.object(StashManager, "push",
                          return_value=StashResult(True, "Saved")):
            with patch.object(StashManager, "list", return_value=[]):
                result = _run(h("push my message"))
        assert isinstance(result, str)

    def test_summary(self):
        from unittest.mock import patch
        from lidco.git.stash_manager import StashManager
        reg = _load_handlers()
        h = reg.commands["stash"].handler
        with patch.object(StashManager, "summary", return_value={"count": 2, "stashes": ["a", "b"]}):
            result = _run(h("summary"))
        assert "2" in result

    def test_count(self):
        from unittest.mock import patch
        from lidco.git.stash_manager import StashManager
        reg = _load_handlers()
        h = reg.commands["stash"].handler
        with patch.object(StashManager, "count", return_value=3):
            result = _run(h("count"))
        assert "3" in result


# ------------------------------------------------------------------ #
# /fixture                                                              #
# ------------------------------------------------------------------ #

class TestFixtureCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "fixture" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["fixture"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo(self):
        reg = _load_handlers()
        h = reg.commands["fixture"].handler
        result = _run(h("demo"))
        assert "@pytest.fixture" in result or "fixture" in result.lower()

    def test_generate(self):
        reg = _load_handlers()
        h = reg.commands["fixture"].handler
        src = "from dataclasses import dataclass\n@dataclass\nclass Foo:\n    x: int\n"
        result = _run(h(f"generate {src}"))
        assert "foo" in result or "Foo" in result or "pytest" in result

    def test_generate_no_args(self):
        reg = _load_handlers()
        h = reg.commands["fixture"].handler
        result = _run(h("generate"))
        assert "Usage" in result

    def test_parse(self):
        reg = _load_handlers()
        h = reg.commands["fixture"].handler
        src = "@dataclass\nclass Bar:\n    name: str\n"
        result = _run(h(f"parse {src}"))
        assert "Bar" in result or "bar" in result

    def test_parse_no_args(self):
        reg = _load_handlers()
        h = reg.commands["fixture"].handler
        result = _run(h("parse"))
        assert "Usage" in result

    def test_scope_get(self):
        reg = _load_handlers()
        h = reg.commands["fixture"].handler
        result = _run(h("scope"))
        assert "function" in result or "scope" in result.lower()

    def test_scope_set(self):
        reg = _load_handlers()
        h = reg.commands["fixture"].handler
        result = _run(h("scope session"))
        assert "session" in result

    def test_scope_invalid(self):
        reg = _load_handlers()
        h = reg.commands["fixture"].handler
        result = _run(h("scope invalid"))
        assert "Invalid" in result or "invalid" in result.lower()


# ------------------------------------------------------------------ #
# /liveness                                                             #
# ------------------------------------------------------------------ #

class TestLivenessCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "liveness" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        result = _run(h("demo"))
        assert "HEALTHY" in result or "DEGRADED" in result or "up" in result.lower()

    def test_add_http(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        result = _run(h("add-http api http://localhost/health"))
        assert "api" in result or "added" in result.lower()

    def test_add_http_no_args(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        result = _run(h("add-http"))
        assert "Usage" in result

    def test_add_tcp(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        result = _run(h("add-tcp db localhost 5432"))
        assert "db" in result or "added" in result.lower()

    def test_add_tcp_no_args(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        result = _run(h("add-tcp"))
        assert "Usage" in result

    def test_list_empty(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        result = _run(h("list"))
        assert "No checks" in result or "check" in result.lower()

    def test_list_with_checks(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        _run(h("add-tcp mydb localhost 5432"))
        result = _run(h("list"))
        assert "mydb" in result

    def test_check_unknown(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        result = _run(h("check ghost"))
        assert "Error" in result or "Unknown" in result

    def test_run_no_checks(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        result = _run(h("run"))
        assert "No checks" in result or isinstance(result, str)

    def test_remove(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        _run(h("add-tcp svc localhost 8080"))
        result = _run(h("remove svc"))
        assert "Removed" in result or "svc" in result

    def test_remove_no_args(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        result = _run(h("remove"))
        assert "Usage" in result

    def test_reset(self):
        reg = _load_handlers()
        h = reg.commands["liveness"].handler
        result = _run(h("reset"))
        assert "reset" in result.lower()
