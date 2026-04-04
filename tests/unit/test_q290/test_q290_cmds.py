"""Tests for Q290 CLI commands."""

import asyncio
from unittest.mock import MagicMock, patch

import unittest


def _make_registry():
    registry = MagicMock()
    registered = {}

    def register_async(name, desc, handler):
        registered[name] = handler

    registry.register_async.side_effect = register_async
    registry._handlers = registered
    return registry


def _get(registry, name):
    return registry._handlers[name]


class TestRegisterQ290(unittest.TestCase):
    def test_all_commands_registered(self):
        from lidco.cli.commands.q290_cmds import register_q290_commands

        r = _make_registry()
        register_q290_commands(r)
        self.assertIn("gl-mr", r._handlers)
        self.assertIn("gl-issue", r._handlers)
        self.assertIn("gl-pipeline", r._handlers)
        self.assertIn("gl-wiki", r._handlers)


class TestGlMrCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q290_cmds import register_q290_commands

        r = _make_registry()
        register_q290_commands(r)
        return _get(r, "gl-mr")

    def test_no_args_shows_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        self.assertIn("Usage", result)

    def test_create(self):
        h = self._handler()
        result = asyncio.run(h("create feat-title feature/branch"))
        self.assertIn("Created MR", result)
        self.assertIn("feat-title", result)

    def test_create_missing_args(self):
        h = self._handler()
        result = asyncio.run(h("create only-title"))
        self.assertIn("Error", result)

    def test_describe(self):
        h = self._handler()
        result = asyncio.run(h('describe "+added"'))
        self.assertIn("Auto-generated", result) or self.assertIn("addition", result.lower())

    def test_unknown_subcommand(self):
        h = self._handler()
        result = asyncio.run(h("bogus"))
        self.assertIn("Unknown subcommand", result)

    def test_create_same_branch_error(self):
        h = self._handler()
        result = asyncio.run(h("create title main main"))
        self.assertIn("Error", result)

    def test_approve_missing_mr(self):
        h = self._handler()
        result = asyncio.run(h("approve 999"))
        self.assertIn("Error", result)

    def test_reviewers_missing_args(self):
        h = self._handler()
        result = asyncio.run(h("reviewers"))
        self.assertIn("Error", result)


class TestGlIssueCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q290_cmds import register_q290_commands

        r = _make_registry()
        register_q290_commands(r)
        return _get(r, "gl-issue")

    def test_no_args_shows_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        self.assertIn("Usage", result)

    def test_list(self):
        h = self._handler()
        result = asyncio.run(h("list"))
        self.assertIn("Listing", result)

    def test_create(self):
        h = self._handler()
        result = asyncio.run(h("create Bug in login"))
        self.assertIn("Created", result)

    def test_close(self):
        h = self._handler()
        result = asyncio.run(h("close 42"))
        self.assertIn("Closed", result)

    def test_create_missing_title(self):
        h = self._handler()
        result = asyncio.run(h("create"))
        self.assertIn("Error", result)

    def test_unknown_subcommand(self):
        h = self._handler()
        result = asyncio.run(h("zap"))
        self.assertIn("Unknown subcommand", result)

    def test_list_with_state(self):
        h = self._handler()
        result = asyncio.run(h("list closed"))
        self.assertIn("closed", result)

    def test_close_missing_id(self):
        h = self._handler()
        result = asyncio.run(h("close"))
        self.assertIn("Error", result)


class TestGlPipelineCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q290_cmds import register_q290_commands

        r = _make_registry()
        register_q290_commands(r)
        return _get(r, "gl-pipeline")

    def test_no_args_shows_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        self.assertIn("Usage", result)

    def test_list_empty(self):
        h = self._handler()
        result = asyncio.run(h("list 1"))
        self.assertIn("No pipelines", result)

    def test_status_missing(self):
        h = self._handler()
        result = asyncio.run(h("status 999"))
        self.assertIn("Error", result)

    def test_logs_missing_job(self):
        h = self._handler()
        result = asyncio.run(h("logs 999"))
        self.assertIn("Error", result)

    def test_retry_missing_job(self):
        h = self._handler()
        result = asyncio.run(h("retry 999"))
        self.assertIn("Error", result)

    def test_unknown_subcommand(self):
        h = self._handler()
        result = asyncio.run(h("explode"))
        self.assertIn("Unknown subcommand", result)

    def test_list_bad_id(self):
        h = self._handler()
        result = asyncio.run(h("list abc"))
        self.assertIn("Error", result)

    def test_list_missing_args(self):
        h = self._handler()
        result = asyncio.run(h("list"))
        self.assertIn("Error", result)


class TestGlWikiCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q290_cmds import register_q290_commands

        r = _make_registry()
        register_q290_commands(r)
        return _get(r, "gl-wiki")

    def test_no_args_shows_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        self.assertIn("Usage", result)

    def test_list_empty(self):
        h = self._handler()
        result = asyncio.run(h("list"))
        self.assertIn("No wiki pages", result)

    def test_get_missing(self):
        h = self._handler()
        result = asyncio.run(h("get nonexistent"))
        self.assertIn("Error", result)

    def test_create_success(self):
        h = self._handler()
        result = asyncio.run(h('create Setup "install instructions"'))
        self.assertIn("Created wiki page", result)

    def test_create_missing_args(self):
        h = self._handler()
        result = asyncio.run(h("create"))
        self.assertIn("Error", result)

    def test_update_missing(self):
        h = self._handler()
        result = asyncio.run(h("update nope content"))
        self.assertIn("Error", result)

    def test_search_no_results(self):
        h = self._handler()
        result = asyncio.run(h("search zzz"))
        self.assertIn("No wiki pages matched", result)

    def test_unknown_subcommand(self):
        h = self._handler()
        result = asyncio.run(h("nuke"))
        self.assertIn("Unknown subcommand", result)


if __name__ == "__main__":
    unittest.main()
