"""Tests for src/lidco/cli/commands/q330_cmds.py — /tour, /explain-concept, /setup-dev, /contrib-guide."""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, object] = {}

    def register_async(self, name: str, description: str, handler: object) -> None:
        self.commands[name] = handler


def _run(coro):
    return asyncio.run(coro)


class TestQ330Registration(unittest.TestCase):
    def test_registers_all_commands(self) -> None:
        from lidco.cli.commands.q330_cmds import register_q330_commands

        reg = _FakeRegistry()
        register_q330_commands(reg)
        self.assertIn("tour", reg.commands)
        self.assertIn("explain-concept", reg.commands)
        self.assertIn("setup-dev", reg.commands)
        self.assertIn("contrib-guide", reg.commands)


class TestTourCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q330_cmds import register_q330_commands

        reg = _FakeRegistry()
        register_q330_commands(reg)
        return reg.commands["tour"]

    def test_no_args(self) -> None:
        result = _run(self._handler()(""))
        self.assertIn("Usage:", result)

    def test_start(self) -> None:
        result = _run(self._handler()("start /myproject"))
        self.assertIn("Tour started", result)
        self.assertIn("/myproject", result)

    def test_start_default(self) -> None:
        result = _run(self._handler()("start"))
        self.assertIn("Tour started", result)

    def test_add_stop(self) -> None:
        result = _run(self._handler()("add cli src/cli.py 'CLI module' --category ui --order 1"))
        self.assertIn("Added stop", result)
        self.assertIn("cli", result)
        self.assertIn("category=ui", result)
        self.assertIn("order=1", result)

    def test_add_stop_missing_args(self) -> None:
        result = _run(self._handler()("add cli"))
        self.assertIn("Usage:", result)

    def test_add_stop_bad_order(self) -> None:
        result = _run(self._handler()("add cli src/cli.py desc --order abc"))
        self.assertIn("Invalid order", result)

    def test_visit(self) -> None:
        result = _run(self._handler()("visit cli"))
        self.assertIn("not found", result)

    def test_visit_missing_args(self) -> None:
        result = _run(self._handler()("visit"))
        self.assertIn("Usage:", result)

    def test_next(self) -> None:
        result = _run(self._handler()("next"))
        self.assertIn("no stops", result.lower())

    def test_list(self) -> None:
        result = _run(self._handler()("list"))
        self.assertIn("No stops", result)

    def test_overview(self) -> None:
        result = _run(self._handler()("overview"))
        self.assertIn("Architecture", result)

    def test_progress(self) -> None:
        result = _run(self._handler()("progress"))
        self.assertIn("Tour", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self._handler()("badcmd"))
        self.assertIn("Unknown subcommand", result)


class TestExplainConceptCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q330_cmds import register_q330_commands

        reg = _FakeRegistry()
        register_q330_commands(reg)
        return reg.commands["explain-concept"]

    def test_no_args(self) -> None:
        result = _run(self._handler()(""))
        self.assertIn("Usage:", result)

    def test_list(self) -> None:
        result = _run(self._handler()("list"))
        self.assertIn("No concepts", result)

    def test_show_missing(self) -> None:
        result = _run(self._handler()("show foo"))
        self.assertIn("not found", result)

    def test_show_no_name(self) -> None:
        result = _run(self._handler()("show"))
        self.assertIn("Usage:", result)

    def test_quiz_missing(self) -> None:
        result = _run(self._handler()("quiz foo"))
        self.assertIn("No quiz", result)

    def test_quiz_no_name(self) -> None:
        result = _run(self._handler()("quiz"))
        self.assertIn("Usage:", result)

    def test_search_missing(self) -> None:
        result = _run(self._handler()("search zzz"))
        self.assertIn("No concepts", result)

    def test_search_no_query(self) -> None:
        result = _run(self._handler()("search"))
        self.assertIn("Usage:", result)

    def test_glossary_empty(self) -> None:
        result = _run(self._handler()("glossary"))
        self.assertIn("empty", result.lower())

    def test_glossary_missing_term(self) -> None:
        result = _run(self._handler()("glossary xyz"))
        self.assertIn("not found", result)

    def test_path(self) -> None:
        result = _run(self._handler()("path"))
        self.assertIn("No concepts", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self._handler()("badcmd"))
        self.assertIn("Unknown subcommand", result)


class TestSetupDevCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q330_cmds import register_q330_commands

        reg = _FakeRegistry()
        register_q330_commands(reg)
        return reg.commands["setup-dev"]

    def test_no_args(self) -> None:
        result = _run(self._handler()(""))
        self.assertIn("Usage:", result)

    @mock.patch("lidco.onboard.setup.shutil.which", return_value="/usr/bin/python")
    def test_check_found(self, _w: mock.MagicMock) -> None:
        result = _run(self._handler()("check python"))
        self.assertIn("[PASS]", result)

    @mock.patch("lidco.onboard.setup.shutil.which", return_value=None)
    def test_check_not_found(self, _w: mock.MagicMock) -> None:
        result = _run(self._handler()("check badcmd"))
        self.assertIn("[FAIL]", result)

    def test_check_no_cmd(self) -> None:
        result = _run(self._handler()("check"))
        self.assertIn("Usage:", result)

    def test_python_check(self) -> None:
        result = _run(self._handler()("python 3.0"))
        self.assertIn("[PASS]", result)

    def test_python_check_default(self) -> None:
        result = _run(self._handler()("python"))
        self.assertIn("PASS", result)

    def test_file_no_path(self) -> None:
        result = _run(self._handler()("file"))
        self.assertIn("Usage:", result)

    def test_file_not_found(self) -> None:
        result = _run(self._handler()("file nonexistent.txt"))
        self.assertIn("[FAIL]", result)

    def test_run_all_empty(self) -> None:
        result = _run(self._handler()("run-all"))
        self.assertIn("No checks", result)

    def test_config_list(self) -> None:
        result = _run(self._handler()("config list"))
        self.assertIn("No config templates", result)

    def test_config_generate_missing(self) -> None:
        result = _run(self._handler()("config generate mytemplate"))
        self.assertIn("not found", result)

    def test_config_no_sub(self) -> None:
        result = _run(self._handler()("config"))
        self.assertIn("Usage:", result)

    def test_config_generate_no_name(self) -> None:
        result = _run(self._handler()("config generate"))
        self.assertIn("Usage:", result)

    def test_config_unknown_sub(self) -> None:
        result = _run(self._handler()("config badcmd"))
        self.assertIn("Unknown config subcommand", result)

    def test_verify(self) -> None:
        result = _run(self._handler()("verify"))
        self.assertIn("Setup Assistant", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self._handler()("badcmd"))
        self.assertIn("Unknown subcommand", result)


class TestContribGuideCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q330_cmds import register_q330_commands

        reg = _FakeRegistry()
        register_q330_commands(reg)
        return reg.commands["contrib-guide"]

    def test_no_args(self) -> None:
        result = _run(self._handler()(""))
        self.assertIn("Usage:", result)

    def test_generate(self) -> None:
        result = _run(self._handler()("generate myproject"))
        self.assertIn("# Contributing to myproject", result)

    def test_generate_default_name(self) -> None:
        result = _run(self._handler()("generate"))
        self.assertIn("# Contributing to project", result)

    def test_default(self) -> None:
        result = _run(self._handler()("default lidco"))
        self.assertIn("# Contributing to lidco", result)
        self.assertIn("Workflow", result)
        self.assertIn("Conventions", result)

    def test_default_default_name(self) -> None:
        result = _run(self._handler()("default"))
        self.assertIn("# Contributing to project", result)

    def test_summary(self) -> None:
        result = _run(self._handler()("summary"))
        self.assertIn("Contribution Guide Generator", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self._handler()("badcmd"))
        self.assertIn("Unknown subcommand", result)


if __name__ == "__main__":
    unittest.main()
