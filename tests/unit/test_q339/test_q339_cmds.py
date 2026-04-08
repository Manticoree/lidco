"""Tests for Q339 CLI commands (Task 1807)."""
from __future__ import annotations

import asyncio
import json
import unittest


class _FakeRegistry:
    """Minimal registry stub."""

    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = (description, handler)


def _run(coro):
    return asyncio.run(coro)


class TestQ339Registration(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q339_cmds import register_q339_commands
        self.reg = _FakeRegistry()
        register_q339_commands(self.reg)

    def test_all_four_commands_registered(self):
        expected = {"config-race", "event-loop-check", "import-cycles", "memory-leaks"}
        self.assertEqual(set(self.reg.commands.keys()), expected)

    def test_descriptions_are_strings(self):
        for name, (desc, _) in self.reg.commands.items():
            self.assertIsInstance(desc, str)
            self.assertGreater(len(desc), 0)


class TestConfigRaceCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q339_cmds import register_q339_commands
        self.reg = _FakeRegistry()
        register_q339_commands(self.reg)
        self.handler = self.reg.commands["config-race"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_with_safe_code(self):
        code = "x = 1\ny = x + 2\n"
        result = _run(self.handler(code))
        self.assertIn("Race", result)

    def test_with_unsafe_code(self):
        code = "config['key'] = value\n"
        result = _run(self.handler(code))
        self.assertIn("Race", result)

    def test_returns_string(self):
        result = _run(self.handler("config['x'] = 1"))
        self.assertIsInstance(result, str)

    def test_missing_file_returns_error(self):
        result = _run(self.handler("--file /nonexistent/path/to/file.py"))
        self.assertIn("Error", result)


class TestEventLoopCheckCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q339_cmds import register_q339_commands
        self.reg = _FakeRegistry()
        register_q339_commands(self.reg)
        self.handler = self.reg.commands["event-loop-check"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_clean_code(self):
        code = "asyncio.run(main())\n"
        result = _run(self.handler(code))
        self.assertIn("Event Loop", result)

    def test_deprecated_pattern_detected(self):
        code = "loop = asyncio.get_event_loop()\nloop.run_until_complete(main())\n"
        result = _run(self.handler(code))
        self.assertIn("Conflicts", result)

    def test_returns_string(self):
        result = _run(self.handler("x = 1"))
        self.assertIsInstance(result, str)

    def test_missing_file_returns_error(self):
        result = _run(self.handler("--file /nonexistent_q339_file.py"))
        self.assertIn("Error", result)


class TestImportCyclesCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q339_cmds import register_q339_commands
        self.reg = _FakeRegistry()
        register_q339_commands(self.reg)
        self.handler = self.reg.commands["import-cycles"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_no_cycle_graph(self):
        graph = json.dumps({"a": ["b"], "b": ["c"], "c": []})
        result = _run(self.handler(graph))
        self.assertIn("No import cycles", result)

    def test_cycle_detected(self):
        graph = json.dumps({"a": ["b"], "b": ["a"]})
        result = _run(self.handler(graph))
        self.assertIn("Cycle", result)

    def test_invalid_json_returns_error(self):
        result = _run(self.handler("not valid json"))
        self.assertIn("Error", result)

    def test_non_dict_json_returns_error(self):
        result = _run(self.handler('["a", "b"]'))
        self.assertIn("Error", result)

    def test_returns_string(self):
        graph = json.dumps({"x": []})
        result = _run(self.handler(graph))
        self.assertIsInstance(result, str)

    def test_cycle_shows_break_suggestion(self):
        graph = json.dumps({"a": ["b"], "b": ["a"]})
        result = _run(self.handler(graph))
        self.assertIn("Break", result)


class TestMemoryLeaksCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q339_cmds import register_q339_commands
        self.reg = _FakeRegistry()
        register_q339_commands(self.reg)
        self.handler = self.reg.commands["memory-leaks"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_clean_code(self):
        result = _run(self.handler("x = 1\n"))
        self.assertIn("Memory Leak", result)

    def test_leak_pattern_detected(self):
        code = "self.children.append(self)\n"
        result = _run(self.handler(code))
        self.assertIn("Reference", result)

    def test_threshold_flag(self):
        result = _run(self.handler("--threshold 50"))
        self.assertIn("GC Stats", result)

    def test_invalid_threshold_returns_error(self):
        result = _run(self.handler("--threshold notanumber"))
        self.assertIn("Error", result)

    def test_missing_file_returns_error(self):
        result = _run(self.handler("--file /no_such_file_q339.py"))
        self.assertIn("Error", result)

    def test_returns_string(self):
        result = _run(self.handler("x = 1"))
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
