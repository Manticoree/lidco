"""Tests for Q189 CLI commands — task 1061."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from lidco.cli.commands import q189_cmds


def _run(coro):
    return asyncio.run(coro)


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ189Registration(unittest.TestCase):
    def setUp(self):
        # Reset module-level state between tests
        q189_cmds._state.clear()

    def test_register_adds_commands(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        self.assertIn("session-server", reg.commands)
        self.assertIn("remote-control", reg.commands)
        self.assertIn("mobile", reg.commands)
        self.assertIn("deep-link", reg.commands)

    def test_session_server_no_args(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["session-server"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_session_server_start(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["session-server"].handler
        result = _run(handler("start"))
        self.assertIn("started", result)

    def test_session_server_status(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["session-server"].handler
        _run(handler("start"))
        result = _run(handler("status"))
        self.assertIn("running", result)

    def test_session_server_stop(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["session-server"].handler
        _run(handler("start"))
        result = _run(handler("stop"))
        self.assertIn("stopped", result)

    def test_session_server_stop_not_running(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["session-server"].handler
        result = _run(handler("stop"))
        self.assertIn("No session server", result)

    def test_remote_control_no_server(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["remote-control"].handler
        result = _run(handler("hello"))
        self.assertIn("Error", result)

    def test_remote_control_with_server(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        srv_handler = reg.commands["session-server"].handler
        _run(srv_handler("start"))
        handler = reg.commands["remote-control"].handler
        result = _run(handler("test message"))
        self.assertIn("Sent", result)

    def test_remote_control_no_message(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        srv_handler = reg.commands["session-server"].handler
        _run(srv_handler("start"))
        handler = reg.commands["remote-control"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_mobile_no_args(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["mobile"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_mobile_pair(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        srv_handler = reg.commands["session-server"].handler
        _run(srv_handler("start"))
        handler = reg.commands["mobile"].handler
        result = _run(handler("pair"))
        self.assertIn("Pairing code", result)

    def test_deep_link_no_args(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["deep-link"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_deep_link_parse(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["deep-link"].handler
        result = _run(handler("parse lidco://open?file=x"))
        self.assertIn("Action: open", result)

    def test_deep_link_generate(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["deep-link"].handler
        result = _run(handler("generate session"))
        self.assertIn("lidco://session", result)

    def test_deep_link_validate(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["deep-link"].handler
        result = _run(handler("validate lidco://open"))
        self.assertIn("True", result)

    def test_session_server_already_running(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["session-server"].handler
        _run(handler("start"))
        result = _run(handler("start"))
        self.assertIn("already running", result)

    def test_session_server_unknown_subcmd(self):
        reg = _FakeRegistry()
        q189_cmds.register(reg)
        handler = reg.commands["session-server"].handler
        result = _run(handler("bogus"))
        self.assertIn("Unknown", result)


if __name__ == "__main__":
    unittest.main()
