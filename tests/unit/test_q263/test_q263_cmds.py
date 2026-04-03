"""Tests for Q263 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q263_cmds import register, _state


class TestQ263Commands(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.registry = MagicMock()
        register(self.registry)
        self.commands = {}
        for call in self.registry.register.call_args_list:
            cmd = call[0][0]
            self.commands[cmd.name] = cmd.handler

    def _run(self, name: str, args: str) -> str:
        return asyncio.run(self.commands[name](args))

    def test_net_inspect_url(self):
        result = self._run("net-inspect", "https://api.openai.com/v1")
        self.assertIn("OK", result)
        self.assertIn("api.openai.com", result)

    def test_net_inspect_history(self):
        self._run("net-inspect", "https://example.com")
        result = self._run("net-inspect", "history")
        self.assertIn("history", result.lower())

    def test_net_inspect_clear(self):
        self._run("net-inspect", "https://example.com")
        result = self._run("net-inspect", "clear")
        self.assertIn("Cleared", result)

    def test_proxy_config_add_list(self):
        result = self._run("proxy-config", "add myproxy http://proxy:8080")
        self.assertIn("Added", result)
        result = self._run("proxy-config", "list")
        self.assertIn("myproxy", result)

    def test_proxy_config_remove(self):
        self._run("proxy-config", "add p1 http://proxy:80")
        result = self._run("proxy-config", "remove p1")
        self.assertIn("Removed", result)

    def test_certs_add_list(self):
        result = self._run("certs", "add test-cert")
        self.assertIn("Registered", result)
        result = self._run("certs", "list")
        self.assertIn("test-cert", result)

    def test_certs_remove(self):
        self._run("certs", "add mycert")
        result = self._run("certs", "remove mycert")
        self.assertIn("Removed", result)

    def test_net_policy_add_eval(self):
        self._run("net-policy", "add evil.com deny")
        result = self._run("net-policy", "eval evil.com")
        self.assertIn("DENIED", result)

    def test_net_policy_list(self):
        self._run("net-policy", "add example.com allow")
        result = self._run("net-policy", "list")
        self.assertIn("example.com", result)

    def test_all_commands_registered(self):
        expected = {"net-inspect", "proxy-config", "certs", "net-policy"}
        self.assertEqual(set(self.commands.keys()), expected)


if __name__ == "__main__":
    unittest.main()
