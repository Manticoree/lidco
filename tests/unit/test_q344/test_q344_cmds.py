"""Tests for Q344 CLI commands."""
from __future__ import annotations

import asyncio
import unittest


def _run(coro):
    return asyncio.run(coro)


class _FakeRegistry:
    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = (description, handler)


class TestQ344Registration(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q344_cmds import register_q344_commands
        self.reg = _FakeRegistry()
        register_q344_commands(self.reg)

    def test_all_four_commands_registered(self):
        expected = {"schema-validate", "config-guard", "session-validate", "cache-coherence"}
        self.assertEqual(set(self.reg.commands.keys()), expected)

    def test_all_descriptions_non_empty(self):
        for name, (desc, _) in self.reg.commands.items():
            self.assertTrue(len(desc) > 0, f"'{name}' has empty description")


class TestSchemaValidateCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q344_cmds import register_q344_commands
        reg = _FakeRegistry()
        register_q344_commands(reg)
        self.handler = reg.commands["schema-validate"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_demo_runs_successfully(self):
        result = _run(self.handler("demo"))
        self.assertIn("Schema Upgrade Validation", result)

    def test_invalid_json_returns_error(self):
        result = _run(self.handler("{bad json}"))
        self.assertIn("Error", result)

    def test_valid_json_shows_result(self):
        import json
        payload = json.dumps({
            "old": {"tables": {"t": [{"name": "id", "type": "INT", "nullable": False}]}},
            "new": {"tables": {"t": [{"name": "id", "type": "BIGINT", "nullable": False}]}},
        })
        result = _run(self.handler(payload))
        self.assertIn("Schema Upgrade Validation", result)


class TestConfigGuardCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q344_cmds import register_q344_commands
        reg = _FakeRegistry()
        register_q344_commands(reg)
        self.handler = reg.commands["config-guard"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_demo_runs_successfully(self):
        result = _run(self.handler("demo"))
        self.assertIn("Config Corruption Guard Demo", result)

    def test_detect_valid_json(self):
        result = _run(self.handler('detect json {"x": 1}'))
        self.assertIn("valid: True", result)

    def test_detect_invalid_json(self):
        result = _run(self.handler('detect json {bad}'))
        self.assertIn("valid: False", result)

    def test_unknown_subcommand_returns_error(self):
        result = _run(self.handler("unknown"))
        self.assertIn("Unknown subcommand", result)


class TestSessionValidateCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q344_cmds import register_q344_commands
        reg = _FakeRegistry()
        register_q344_commands(reg)
        self.handler = reg.commands["session-validate"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_demo_runs_successfully(self):
        result = _run(self.handler("demo"))
        self.assertIn("Session State Validation Demo", result)

    def test_invalid_json_returns_error(self):
        result = _run(self.handler("{not json}"))
        self.assertIn("Error", result)


class TestCacheCoherenceCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q344_cmds import register_q344_commands
        reg = _FakeRegistry()
        register_q344_commands(reg)
        self.handler = reg.commands["cache-coherence"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_demo_runs_successfully(self):
        result = _run(self.handler("demo"))
        self.assertIn("Cache Coherence Demo", result)

    def test_consistent_payload(self):
        import json
        payload = json.dumps({"cache": {"a": 1}, "source": {"a": 1}})
        result = _run(self.handler(payload))
        self.assertIn("CONSISTENT", result)

    def test_inconsistent_payload(self):
        import json
        payload = json.dumps({"cache": {"a": 99}, "source": {"a": 1}})
        result = _run(self.handler(payload))
        self.assertIn("INCONSISTENT", result)
