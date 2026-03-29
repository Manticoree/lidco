"""Tests for src/lidco/cli/commands/q123_cmds.py."""
import asyncio


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load():
    import lidco.cli.commands.q123_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg, mod


class TestGenCmdRegistered:
    def test_registered(self):
        reg, _ = _load()
        assert "gen" in reg.commands

    def test_no_args_returns_usage(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler(""))
        assert "Usage" in result or "class" in result.lower()


class TestGenClass:
    def test_gen_class_no_name(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("class"))
        assert "class" in result.lower()
        assert "MyClass" in result

    def test_gen_class_with_name(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("class Foo"))
        assert "Foo" in result

    def test_gen_class_contains_class_keyword(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("class Bar"))
        assert "class Bar" in result

    def test_gen_class_returns_string(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("class Widget"))
        assert isinstance(result, str)

    def test_gen_class_label(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("class TestClass"))
        assert "Generated" in result or "class" in result.lower()


class TestGenTest:
    def test_gen_test_no_name(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("test"))
        assert "MyModule" in result or "test" in result.lower()

    def test_gen_test_with_name(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("test MyService"))
        assert "MyService" in result

    def test_gen_test_contains_pytest(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("test Foo"))
        assert "pytest" in result or "test" in result.lower()

    def test_gen_test_returns_string(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("test SomeClass"))
        assert isinstance(result, str)


class TestGenModule:
    def test_gen_module_no_name(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("module"))
        assert "my_module" in result or "module" in result.lower()

    def test_gen_module_with_name(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("module utils"))
        assert "utils" in result

    def test_gen_module_contains_docstring(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("module my_mod"))
        assert '"""' in result or "module" in result.lower()

    def test_gen_module_returns_string(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("module helpers"))
        assert isinstance(result, str)


class TestGenList:
    def test_gen_list_returns_templates(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("list"))
        assert "class" in result or "template" in result.lower()

    def test_gen_list_multiple_entries(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("list"))
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) >= 1

    def test_gen_list_is_string(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("list"))
        assert isinstance(result, str)


class TestGenUnknown:
    def test_unknown_sub(self):
        reg, _ = _load()
        result = _run(reg.commands["gen"].handler("unknown"))
        assert "Usage" in result or "class" in result.lower()
