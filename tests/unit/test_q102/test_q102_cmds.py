"""Tests for src/lidco/cli/commands/q102_cmds.py."""
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
    import lidco.cli.commands.q102_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg


class TestContainerCommand:
    def test_register_and_resolve(self):
        reg = _load_handlers()
        handler = reg.commands["container"].handler
        _run(handler("register mykey myvalue"))
        result = _run(handler("resolve mykey"))
        assert "myvalue" in result

    def test_resolve_unknown(self):
        reg = _load_handlers()
        handler = reg.commands["container"].handler
        result = _run(handler("resolve no_such_key"))
        assert "Error" in result

    def test_list_empty(self):
        reg = _load_handlers()
        handler = reg.commands["container"].handler
        result = _run(handler("list"))
        assert "empty" in result

    def test_list_with_items(self):
        reg = _load_handlers()
        handler = reg.commands["container"].handler
        _run(handler("register x 1"))
        result = _run(handler("list"))
        assert "x" in result

    def test_clear(self):
        reg = _load_handlers()
        handler = reg.commands["container"].handler
        _run(handler("register x 1"))
        result = _run(handler("clear"))
        assert "cleared" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["container"].handler
        result = _run(handler(""))
        assert "Usage" in result

    def test_unknown_subcommand(self):
        reg = _load_handlers()
        handler = reg.commands["container"].handler
        result = _run(handler("badcmd"))
        assert "Unknown" in result


class TestPluginsCommand:
    def test_list_empty(self):
        reg = _load_handlers()
        handler = reg.commands["plugins"].handler
        result = _run(handler("list"))
        assert "no plugins" in result.lower()

    def test_load_bad_path(self):
        reg = _load_handlers()
        handler = reg.commands["plugins"].handler
        result = _run(handler("load /nonexistent/path"))
        assert "not found" in result.lower() or "Path" in result

    def test_load_valid_path(self, tmp_path):
        (tmp_path / "myplugin.py").write_text(
            "class MyPlugin:\n    plugin_name = 'my_plugin'\n"
        )
        reg = _load_handlers()
        handler = reg.commands["plugins"].handler
        result = _run(handler(f"load {tmp_path}"))
        assert "my_plugin" in result or "1 plugin" in result

    def test_info_missing(self):
        reg = _load_handlers()
        handler = reg.commands["plugins"].handler
        result = _run(handler("info not_a_plugin"))
        assert "not found" in result.lower()

    def test_clear(self):
        reg = _load_handlers()
        handler = reg.commands["plugins"].handler
        result = _run(handler("clear"))
        assert "cleared" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["plugins"].handler
        result = _run(handler(""))
        assert "Usage" in result

    def test_unknown_subcommand(self):
        reg = _load_handlers()
        handler = reg.commands["plugins"].handler
        result = _run(handler("badcmd"))
        assert "Unknown" in result


class TestFlagsCommand:
    def test_list_empty(self):
        reg = _load_handlers()
        handler = reg.commands["flags"].handler
        result = _run(handler("list"))
        assert "no flags" in result.lower()

    def test_define_and_list(self):
        reg = _load_handlers()
        handler = reg.commands["flags"].handler
        _run(handler("define my_feature --rollout 100"))
        result = _run(handler("list"))
        assert "my_feature" in result

    def test_check_enabled(self):
        reg = _load_handlers()
        handler = reg.commands["flags"].handler
        _run(handler("define my_feature --rollout 100"))
        result = _run(handler("check my_feature user1"))
        assert "ENABLED" in result

    def test_disable_flag(self):
        reg = _load_handlers()
        handler = reg.commands["flags"].handler
        _run(handler("define my_feature --rollout 100"))
        _run(handler("disable my_feature"))
        result = _run(handler("check my_feature user1"))
        assert "DISABLED" in result

    def test_enable_flag(self):
        reg = _load_handlers()
        handler = reg.commands["flags"].handler
        _run(handler("define my_feature --rollout 100"))
        _run(handler("disable my_feature"))
        _run(handler("enable my_feature"))
        result = _run(handler("check my_feature user1"))
        assert "ENABLED" in result

    def test_remove_flag(self):
        reg = _load_handlers()
        handler = reg.commands["flags"].handler
        _run(handler("define my_feature --rollout 100"))
        result = _run(handler("remove my_feature"))
        assert "True" in result or "Removed" in result

    def test_enable_missing(self):
        reg = _load_handlers()
        handler = reg.commands["flags"].handler
        result = _run(handler("enable no_such_flag"))
        assert "not found" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["flags"].handler
        result = _run(handler(""))
        assert "Usage" in result

    def test_unknown_subcommand(self):
        reg = _load_handlers()
        handler = reg.commands["flags"].handler
        result = _run(handler("badcmd"))
        assert "Unknown" in result


class TestAuditCommand:
    def test_log_and_query(self):
        reg = _load_handlers()
        handler = reg.commands["audit"].handler
        _run(handler("log alice login /auth"))
        result = _run(handler("query"))
        assert "alice" in result

    def test_stats(self):
        reg = _load_handlers()
        handler = reg.commands["audit"].handler
        _run(handler("log alice login /auth"))
        result = _run(handler("stats"))
        assert "Total" in result or "total" in result

    def test_export_json(self):
        reg = _load_handlers()
        handler = reg.commands["audit"].handler
        _run(handler("log alice login /auth"))
        result = _run(handler("export json"))
        import json
        data = json.loads(result)
        assert len(data) >= 1

    def test_export_csv(self):
        reg = _load_handlers()
        handler = reg.commands["audit"].handler
        _run(handler("log alice login /auth"))
        result = _run(handler("export csv"))
        assert "alice" in result

    def test_clear(self):
        reg = _load_handlers()
        handler = reg.commands["audit"].handler
        _run(handler("log alice login /auth"))
        result = _run(handler("clear"))
        assert "Cleared" in result or "cleared" in result.lower()

    def test_query_empty(self):
        reg = _load_handlers()
        handler = reg.commands["audit"].handler
        result = _run(handler("query"))
        assert "no entries" in result.lower() or "empty" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["audit"].handler
        result = _run(handler(""))
        assert "Usage" in result

    def test_unknown_subcommand(self):
        reg = _load_handlers()
        handler = reg.commands["audit"].handler
        result = _run(handler("badcmd"))
        assert "Unknown" in result
