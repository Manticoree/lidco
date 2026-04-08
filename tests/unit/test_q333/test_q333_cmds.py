"""Tests for lidco.cli.commands.q333_cmds — /adr, /gen-adr, /search-adr, /validate-adr."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _run(coro):
    return asyncio.run(coro)


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = (description, handler)


class TestQ333CommandRegistration(unittest.TestCase):
    """All four commands are registered."""

    def setUp(self) -> None:
        from lidco.cli.commands.q333_cmds import register_q333_commands
        self.reg = _FakeRegistry()
        register_q333_commands(self.reg)

    def test_adr_registered(self) -> None:
        self.assertIn("adr", self.reg.commands)

    def test_gen_adr_registered(self) -> None:
        self.assertIn("gen-adr", self.reg.commands)

    def test_search_adr_registered(self) -> None:
        self.assertIn("search-adr", self.reg.commands)

    def test_validate_adr_registered(self) -> None:
        self.assertIn("validate-adr", self.reg.commands)


class TestADRHandler(unittest.TestCase):
    """Tests for /adr handler."""

    def setUp(self) -> None:
        from lidco.cli.commands.q333_cmds import register_q333_commands
        self.reg = _FakeRegistry()
        register_q333_commands(self.reg)
        self.handler = self.reg.commands["adr"][1]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_list_empty(self) -> None:
        result = _run(self.handler("list"))
        self.assertIn("No ADRs", result)

    def test_create(self) -> None:
        result = _run(self.handler('create "Use Redis"'))
        self.assertIn("Created ADR-0001", result)

    def test_show_missing(self) -> None:
        result = _run(self.handler("show"))
        self.assertIn("Usage", result)

    def test_templates(self) -> None:
        result = _run(self.handler("templates"))
        self.assertIn("default", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self.handler("bogus"))
        self.assertIn("Unknown", result)

    def test_accept_missing_num(self) -> None:
        result = _run(self.handler("accept"))
        self.assertIn("Usage", result)

    def test_deprecate_missing_num(self) -> None:
        result = _run(self.handler("deprecate"))
        self.assertIn("Usage", result)

    def test_supersede_missing_args(self) -> None:
        result = _run(self.handler("supersede 1"))
        self.assertIn("Usage", result)

    def test_remove_missing_num(self) -> None:
        result = _run(self.handler("remove"))
        self.assertIn("Usage", result)

    def test_export_missing_num(self) -> None:
        result = _run(self.handler("export"))
        self.assertIn("Usage", result)

    def test_show_not_found(self) -> None:
        result = _run(self.handler("show 999"))
        self.assertIn("not found", result)

    def test_list_invalid_status(self) -> None:
        result = _run(self.handler("list bogus"))
        self.assertIn("Unknown status", result)


class TestGenADRHandler(unittest.TestCase):
    """Tests for /gen-adr handler."""

    def setUp(self) -> None:
        from lidco.cli.commands.q333_cmds import register_q333_commands
        self.reg = _FakeRegistry()
        register_q333_commands(self.reg)
        self.handler = self.reg.commands["gen-adr"][1]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_from_text(self) -> None:
        result = _run(self.handler('from-text "We decided to use Go because performance matters"'))
        self.assertIn("Generated ADR", result)
        self.assertIn("Confidence", result)

    def test_from_text_missing(self) -> None:
        result = _run(self.handler("from-text"))
        self.assertIn("Usage", result)

    def test_from_json_invalid(self) -> None:
        result = _run(self.handler("from-json not-json"))
        self.assertIn("Error", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self.handler("bogus"))
        self.assertIn("Unknown", result)


class TestSearchADRHandler(unittest.TestCase):
    """Tests for /search-adr handler."""

    def setUp(self) -> None:
        from lidco.cli.commands.q333_cmds import register_q333_commands
        self.reg = _FakeRegistry()
        register_q333_commands(self.reg)
        self.handler = self.reg.commands["search-adr"][1]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_search_no_results(self) -> None:
        result = _run(self.handler("nonexistent"))
        self.assertIn("No ADRs", result)

    def test_status_invalid(self) -> None:
        result = _run(self.handler("--status bogus"))
        self.assertIn("Unknown status", result)

    def test_status_missing_arg(self) -> None:
        result = _run(self.handler("--status"))
        self.assertIn("Usage", result)

    def test_tag_missing_arg(self) -> None:
        result = _run(self.handler("--tag"))
        self.assertIn("Usage", result)

    def test_date_missing_args(self) -> None:
        result = _run(self.handler("--date 2020-01-01"))
        self.assertIn("Usage", result)

    def test_trace_empty(self) -> None:
        result = _run(self.handler("--trace"))
        self.assertIn("No ADRs", result)


class TestValidateADRHandler(unittest.TestCase):
    """Tests for /validate-adr handler."""

    def setUp(self) -> None:
        from lidco.cli.commands.q333_cmds import register_q333_commands
        self.reg = _FakeRegistry()
        register_q333_commands(self.reg)
        self.handler = self.reg.commands["validate-adr"][1]

    def test_no_args_empty(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("0 ADRs", result)

    def test_overdue_empty(self) -> None:
        result = _run(self.handler("overdue"))
        self.assertIn("No overdue", result)

    def test_single_invalid(self) -> None:
        result = _run(self.handler("abc"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
