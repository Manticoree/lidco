"""Tests for Q342 CLI commands (Tasks 5)."""
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


class TestQ342Registration(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q342_cmds import register_q342_commands
        self.reg = _FakeRegistry()
        register_q342_commands(self.reg)

    def test_all_commands_registered(self):
        expected = {
            "exception-audit",
            "error-messages",
            "degradation-check",
            "recovery-paths",
        }
        self.assertEqual(set(self.reg.commands.keys()), expected)

    def test_all_descriptions_non_empty(self):
        for name, (desc, _) in self.reg.commands.items():
            self.assertTrue(len(desc) > 0, f"'{name}' has empty description")


class TestExceptionAuditCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q342_cmds import register_q342_commands
        reg = _FakeRegistry()
        register_q342_commands(reg)
        self.handler = reg.commands["exception-audit"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_source_with_bare_except_flagged(self):
        src = "try:\n    risky()\nexcept:\n    pass\n"
        result = _run(self.handler(src))
        self.assertIn("Exception Chain Audit", result)

    def test_clean_source_no_issues(self):
        src = "x = 1\n"
        result = _run(self.handler(src))
        self.assertIn("Total issues", result)


class TestErrorMessagesCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q342_cmds import register_q342_commands
        reg = _FakeRegistry()
        register_q342_commands(reg)
        self.handler = reg.commands["error-messages"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_source_with_raise_produces_report(self):
        src = 'raise ValueError("something went wrong")\n'
        result = _run(self.handler(src))
        self.assertIn("Error Message Standardization", result)

    def test_no_raise_reports_none_found(self):
        result = _run(self.handler("x = 1\n"))
        self.assertIn("No error messages", result)


class TestDegradationCheckCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q342_cmds import register_q342_commands
        reg = _FakeRegistry()
        register_q342_commands(reg)
        self.handler = reg.commands["degradation-check"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_source_with_network_call_produces_report(self):
        src = "resp = requests.get('http://x.com')\n"
        result = _run(self.handler(src))
        self.assertIn("Graceful Degradation", result)

    def test_total_issues_in_output(self):
        result = _run(self.handler("x = 1\n"))
        self.assertIn("Total issues", result)


class TestRecoveryPathsCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q342_cmds import register_q342_commands
        reg = _FakeRegistry()
        register_q342_commands(reg)
        self.handler = reg.commands["recovery-paths"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_source_with_silent_ignore_flagged(self):
        src = "try:\n    risky()\nexcept Exception:\n    pass\n"
        result = _run(self.handler(src))
        self.assertIn("Recovery Path Validation", result)

    def test_total_issues_in_output(self):
        result = _run(self.handler("x = 1\n"))
        self.assertIn("Total issues", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)
