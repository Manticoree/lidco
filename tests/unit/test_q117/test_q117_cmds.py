"""Tests for Q117 CLI commands (Task 721)."""
import asyncio
import json
import unittest

from lidco.hooks.event_bus import HookEvent, HookEventBus
from lidco.hooks.conditional_filter import HookRegistry
from lidco.cli.commands.q117_cmds import register, _state


def _make_registry():
    """Create a mock registry that captures registered commands."""
    commands = {}

    class MockRegistry:
        def register(self, cmd):
            commands[cmd.name] = cmd

    reg = MockRegistry()
    register(reg)
    return commands


def _reset_state():
    """Reset module-level _state to fresh bus and registry."""
    bus = HookEventBus()
    registry = HookRegistry(bus=bus)
    _state["bus"] = bus
    _state["registry"] = registry
    _state.pop("filter_logs", None)


class TestRegistration(unittest.TestCase):
    def test_hook_registered(self):
        cmds = _make_registry()
        self.assertIn("hook", cmds)

    def test_hook_description(self):
        cmds = _make_registry()
        self.assertIn("hook", cmds["hook"].description.lower())


class TestHookList(unittest.TestCase):
    def setUp(self):
        _reset_state()
        self.cmds = _make_registry()
        self.handler = self.cmds["hook"].handler

    def test_list_empty(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("No hooks", result)

    def test_list_shows_registered(self):
        from lidco.hooks.conditional_filter import HookDefinition

        reg = _state["registry"]
        reg.register(HookDefinition(name="test-hook", event_type="click", handler=lambda e: None))
        result = asyncio.run(self.handler("list"))
        self.assertIn("test-hook", result)
        self.assertIn("click", result)

    def test_list_shows_count(self):
        from lidco.hooks.conditional_filter import HookDefinition

        reg = _state["registry"]
        reg.register(HookDefinition(name="h1", event_type="e", handler=lambda e: None))
        result = asyncio.run(self.handler("list"))
        self.assertIn("1", result)

    def test_list_shows_pattern(self):
        from lidco.hooks.conditional_filter import HookDefinition

        reg = _state["registry"]
        reg.register(HookDefinition(name="h1", event_type="e", handler=lambda e: None, if_pattern="abc"))
        result = asyncio.run(self.handler("list"))
        self.assertIn("pattern=abc", result)


class TestHookEmit(unittest.TestCase):
    def setUp(self):
        _reset_state()
        self.cmds = _make_registry()
        self.handler = self.cmds["hook"].handler

    def test_emit_with_payload(self):
        calls = []
        bus = _state["bus"]
        bus.subscribe("test", lambda e: calls.append(e))
        result = asyncio.run(self.handler('emit test {"key":"val"}'))
        self.assertIn("1 handler", result)
        self.assertEqual(len(calls), 1)

    def test_emit_no_subscribers(self):
        result = asyncio.run(self.handler("emit nope {}"))
        self.assertIn("0 handler", result)

    def test_emit_missing_type(self):
        result = asyncio.run(self.handler("emit"))
        self.assertIn("Usage", result)

    def test_emit_invalid_json(self):
        result = asyncio.run(self.handler("emit test {bad}"))
        self.assertIn("Invalid JSON", result)

    def test_emit_default_empty_payload(self):
        result = asyncio.run(self.handler("emit mytype"))
        self.assertIn("0 handler", result)

    def test_emit_non_object_payload(self):
        result = asyncio.run(self.handler('emit test [1,2,3]'))
        self.assertIn("must be a JSON object", result)


class TestHookAddHttp(unittest.TestCase):
    def setUp(self):
        _reset_state()
        self.cmds = _make_registry()
        self.handler = self.cmds["hook"].handler

    def test_add_http_success(self):
        result = asyncio.run(self.handler("add-http click http://hook.example.com"))
        self.assertIn("Registered HTTP hook", result)
        self.assertIn("click", result)

    def test_add_http_missing_args(self):
        result = asyncio.run(self.handler("add-http"))
        self.assertIn("Usage", result)

    def test_add_http_missing_url(self):
        result = asyncio.run(self.handler("add-http click"))
        self.assertIn("Usage", result)

    def test_add_http_shows_in_list(self):
        asyncio.run(self.handler("add-http myevent http://x.com"))
        result = asyncio.run(self.handler("list"))
        self.assertIn("http-myevent", result)


class TestHookAddFilter(unittest.TestCase):
    def setUp(self):
        _reset_state()
        self.cmds = _make_registry()
        self.handler = self.cmds["hook"].handler

    def test_add_filter_success(self):
        result = asyncio.run(self.handler("add-filter click abc"))
        self.assertIn("Registered filter hook", result)
        self.assertIn("abc", result)

    def test_add_filter_missing_args(self):
        result = asyncio.run(self.handler("add-filter"))
        self.assertIn("Usage", result)

    def test_add_filter_missing_pattern(self):
        result = asyncio.run(self.handler("add-filter click"))
        self.assertIn("Usage", result)

    def test_add_filter_shows_in_list(self):
        asyncio.run(self.handler("add-filter evt pat"))
        result = asyncio.run(self.handler("list"))
        self.assertIn("filter-evt", result)

    def test_filter_actually_filters(self):
        asyncio.run(self.handler("add-filter evt keyword"))
        bus = _state["bus"]
        # Emit event that does NOT match
        bus.emit(HookEvent(event_type="evt", payload={"msg": "no match"}))
        logs = _state.get("filter_logs", [])
        self.assertEqual(len(logs), 0)

    def test_filter_fires_on_match(self):
        asyncio.run(self.handler("add-filter evt keyword"))
        bus = _state["bus"]
        bus.emit(HookEvent(event_type="evt", payload={"msg": "has keyword here"}))
        logs = _state.get("filter_logs", [])
        self.assertEqual(len(logs), 1)


class TestHookClear(unittest.TestCase):
    def setUp(self):
        _reset_state()
        self.cmds = _make_registry()
        self.handler = self.cmds["hook"].handler

    def test_clear(self):
        asyncio.run(self.handler("add-http click http://x"))
        result = asyncio.run(self.handler("clear"))
        self.assertIn("cleared", result.lower())

    def test_clear_then_list_empty(self):
        asyncio.run(self.handler("add-http click http://x"))
        asyncio.run(self.handler("clear"))
        result = asyncio.run(self.handler("list"))
        self.assertIn("No hooks", result)


class TestHookUsage(unittest.TestCase):
    def setUp(self):
        _reset_state()
        self.cmds = _make_registry()
        self.handler = self.cmds["hook"].handler

    def test_no_subcommand(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = asyncio.run(self.handler("bogus"))
        self.assertIn("Usage", result)

    def test_usage_lists_subcommands(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("list", result)
        self.assertIn("emit", result)
        self.assertIn("add-http", result)
        self.assertIn("add-filter", result)
        self.assertIn("clear", result)


if __name__ == "__main__":
    unittest.main()
