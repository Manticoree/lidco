"""Tests for Q340 CLI commands (Tasks 1-5)."""
from __future__ import annotations

import asyncio
import json
import unittest


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = (description, handler)


def _run(coro):
    return asyncio.run(coro)


class TestQ340Registration(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q340_cmds import register_q340_commands
        self.reg = _FakeRegistry()
        register_q340_commands(self.reg)

    def test_all_commands_registered(self):
        expected = {"cmd-dedup", "cmd-deps", "async-validate", "cmd-coverage"}
        self.assertEqual(set(self.reg.commands.keys()), expected)

    def test_all_descriptions_non_empty(self):
        for name, (desc, _) in self.reg.commands.items():
            self.assertTrue(len(desc) > 0, f"'{name}' has empty description")


class TestCmdDedupCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q340_cmds import register_q340_commands
        self.reg = _FakeRegistry()
        register_q340_commands(self.reg)
        self.handler = self.reg.commands["cmd-dedup"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_invalid_json_returns_error(self):
        result = _run(self.handler("not-json"))
        self.assertIn("Error", result)

    def test_valid_no_duplicates(self):
        data = json.dumps([
            {"name": "foo", "description": "Foo", "line": 1},
            {"name": "bar", "description": "Bar", "line": 2},
        ])
        result = _run(self.handler(data))
        self.assertIn("No duplicate", result)

    def test_valid_with_duplicates(self):
        data = json.dumps([
            {"name": "foo", "description": "Foo", "line": 1},
            {"name": "foo", "description": "Foo2", "line": 10},
        ])
        result = _run(self.handler(data))
        self.assertIn("foo", result)
        self.assertIn("Duplicates", result)

    def test_non_array_json_returns_error(self):
        result = _run(self.handler('{"not": "an array"}'))
        self.assertIn("Error", result)


class TestCmdDepsCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q340_cmds import register_q340_commands
        self.reg = _FakeRegistry()
        register_q340_commands(self.reg)
        self.handler = self.reg.commands["cmd-deps"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_stdlib_source_no_missing(self):
        source = "import os\nimport sys\n"
        result = _run(self.handler(source))
        self.assertIn("[OK]", result)

    def test_missing_import_flagged(self):
        source = "import _nonexistent_pkg_xyz_abc_q340\n"
        result = _run(self.handler(source))
        self.assertIn("[MISSING]", result)


class TestAsyncValidateCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q340_cmds import register_q340_commands
        self.reg = _FakeRegistry()
        register_q340_commands(self.reg)
        self.handler = self.reg.commands["async-validate"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_clean_code_no_blocking(self):
        source = "async def h():\n    await asyncio.sleep(0)\n"
        result = _run(self.handler(source))
        self.assertIn("No blocking calls", result)

    def test_blocking_call_detected(self):
        source = "async def h():\n    time.sleep(5)\n"
        result = _run(self.handler(source))
        self.assertIn("Blocking calls detected", result)


class TestCmdCoverageCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q340_cmds import register_q340_commands
        self.reg = _FakeRegistry()
        register_q340_commands(self.reg)
        self.handler = self.reg.commands["cmd-coverage"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_invalid_json_returns_error(self):
        result = _run(self.handler("not-json"))
        self.assertIn("Error", result)

    def test_all_covered_shows_100_percent(self):
        data = json.dumps({
            "commands": ["foo"],
            "test_files": {"test_foo.py": "foo handler here"},
        })
        result = _run(self.handler(data))
        self.assertIn("100.0%", result)

    def test_untested_command_shows_stubs(self):
        data = json.dumps({
            "commands": ["missing-cmd"],
            "test_files": {"test_other.py": "nothing here"},
        })
        result = _run(self.handler(data))
        self.assertIn("Untested", result)

    def test_non_dict_json_returns_error(self):
        result = _run(self.handler("[1, 2, 3]"))
        self.assertIn("Error", result)


if __name__ == "__main__":
    unittest.main()
