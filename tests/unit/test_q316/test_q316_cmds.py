"""Tests for lidco.cli.commands.q316_cmds — task 1696."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch


class FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler: object) -> None:
        self.commands[name] = (description, handler)


class TestQ316Registration(unittest.TestCase):
    """Test that all Q316 commands are registered."""

    def test_all_commands_registered(self) -> None:
        from lidco.cli.commands.q316_cmds import register_q316_commands

        reg = FakeRegistry()
        register_q316_commands(reg)

        expected = {"api-test", "api-run", "api-mock", "api-report"}
        self.assertEqual(set(reg.commands.keys()), expected)


class TestApiTestHandler(unittest.TestCase):
    """Test /api-test handler."""

    def _get_handler(self) -> object:
        from lidco.cli.commands.q316_cmds import register_q316_commands

        reg = FakeRegistry()
        register_q316_commands(reg)
        return reg.commands["api-test"][1]

    def test_no_args(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_basic(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("GET https://api.com/test --name my-test"))
        self.assertIn("my-test", result)
        self.assertIn("GET", result)
        self.assertIn("https://api.com/test", result)

    def test_with_assertions(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("POST https://api.com/x --assert-status 201 --assert-body-contains ok"))
        self.assertIn("Assertions: 2", result)

    def test_with_header(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler('GET https://api.com --header "X-Key:val"'))
        self.assertIn("X-Key", result)

    def test_with_body(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler('POST https://api.com --body {"x":1}'))
        self.assertIn("Body", result)


class TestApiRunHandler(unittest.TestCase):
    """Test /api-run handler."""

    def _get_handler(self) -> object:
        from lidco.cli.commands.q316_cmds import register_q316_commands

        reg = FakeRegistry()
        register_q316_commands(reg)
        return reg.commands["api-run"][1]

    def test_no_args(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    @patch("lidco.apitest.runner.urlopen")
    def test_basic_run(self, mock_urlopen: MagicMock) -> None:
        resp = MagicMock()
        resp.status = 200
        resp.read.return_value = b'{"ok":true}'
        resp.getheaders.return_value = [("Content-Type", "application/json")]
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        handler = self._get_handler()
        result = asyncio.run(handler("GET http://localhost/ping --assert-status 200"))
        self.assertIn("PASS", result)

    @patch("lidco.apitest.runner.urlopen")
    def test_failing_assertion(self, mock_urlopen: MagicMock) -> None:
        resp = MagicMock()
        resp.status = 500
        resp.read.return_value = b'"error"'
        resp.getheaders.return_value = []
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        handler = self._get_handler()
        result = asyncio.run(handler("GET http://localhost/fail --assert-status 200"))
        self.assertIn("FAIL", result)


class TestApiMockHandler(unittest.TestCase):
    """Test /api-mock handler."""

    def _get_handler(self) -> object:
        from lidco.cli.commands.q316_cmds import register_q316_commands

        reg = FakeRegistry()
        register_q316_commands(reg)
        return reg.commands["api-mock"][1]

    def test_no_args(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_start_stop(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("start"))
        self.assertIn("started", result)

        result = asyncio.run(handler("stop"))
        self.assertIn("stopped", result)

    def test_stop_without_start(self) -> None:
        handler = self._get_handler()
        # Ensure clean state
        if hasattr(handler, "_server"):
            handler._server = None
        result = asyncio.run(handler("stop"))
        self.assertIn("No mock server", result)

    def test_add_route(self) -> None:
        handler = self._get_handler()
        asyncio.run(handler("start"))
        try:
            result = asyncio.run(handler('add GET /test --status 201 --body {"ok":true}'))
            self.assertIn("Route added", result)
            self.assertIn("201", result)
        finally:
            asyncio.run(handler("stop"))

    def test_add_without_server(self) -> None:
        handler = self._get_handler()
        if hasattr(handler, "_server"):
            handler._server = None
        result = asyncio.run(handler("add GET /x"))
        self.assertIn("No mock server running", result)

    def test_list_routes(self) -> None:
        handler = self._get_handler()
        asyncio.run(handler("start"))
        try:
            asyncio.run(handler("add GET /a"))
            result = asyncio.run(handler("list"))
            self.assertIn("GET /a", result)
        finally:
            asyncio.run(handler("stop"))

    def test_list_empty(self) -> None:
        handler = self._get_handler()
        asyncio.run(handler("start"))
        try:
            # Clear routes_info
            handler._routes_info = []
            result = asyncio.run(handler("list"))
            self.assertIn("No routes", result)
        finally:
            asyncio.run(handler("stop"))

    def test_unknown_subcommand(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler("bogus"))
        self.assertIn("Unknown", result)

    def test_double_start(self) -> None:
        handler = self._get_handler()
        asyncio.run(handler("start"))
        try:
            result = asyncio.run(handler("start"))
            self.assertIn("already running", result)
        finally:
            asyncio.run(handler("stop"))


class TestApiReportHandler(unittest.TestCase):
    """Test /api-report handler."""

    def _get_handler(self) -> object:
        from lidco.cli.commands.q316_cmds import register_q316_commands

        reg = FakeRegistry()
        register_q316_commands(reg)
        return reg.commands["api-report"][1]

    def test_no_results(self) -> None:
        handler = self._get_handler()
        result = asyncio.run(handler(""))
        self.assertIn("No test results", result)


if __name__ == "__main__":
    unittest.main()
