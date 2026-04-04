"""Tests for Q298 CLI commands (Q298)."""
import asyncio
import json
import unittest

from lidco.cli.commands.q298_cmds import register_q298_commands


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ298Commands(unittest.TestCase):
    def setUp(self):
        self.registry = FakeRegistry()
        register_q298_commands(self.registry)

    def _run(self, name, args=""):
        handler = self.registry.commands[name].handler
        return asyncio.run(handler(args))

    # -- /webhook-server -----------------------------------------

    def test_webhook_server_no_args_shows_usage(self):
        result = self._run("webhook-server", "")
        self.assertIn("Usage", result)

    def test_webhook_server_register(self):
        result = self._run("webhook-server", "register /test")
        self.assertIn("registered", result.lower())

    def test_webhook_server_verify(self):
        result = self._run("webhook-server", "verify payload badsig secret")
        self.assertIn("Signature valid:", result)

    def test_webhook_server_pending_empty(self):
        result = self._run("webhook-server", "pending")
        self.assertIn("No pending", result)

    def test_webhook_server_dead_letter_empty(self):
        result = self._run("webhook-server", "dead-letter")
        self.assertIn("No dead-letter", result)

    def test_webhook_server_unknown_subcmd(self):
        result = self._run("webhook-server", "foobar")
        self.assertIn("Unknown", result)

    # -- /webhook-send -------------------------------------------

    def test_webhook_send_no_args_shows_usage(self):
        result = self._run("webhook-send", "")
        self.assertIn("Usage", result)

    def test_webhook_send_log_empty(self):
        result = self._run("webhook-send", "log")
        self.assertIn("No delivery", result)

    # -- /event-route --------------------------------------------

    def test_event_route_no_args_shows_usage(self):
        result = self._run("event-route", "")
        self.assertIn("Usage", result)

    def test_event_route_add(self):
        result = self._run("event-route", "add user.*")
        self.assertIn("Route added", result)

    def test_event_route_unknown_subcmd(self):
        result = self._run("event-route", "foobar")
        self.assertIn("Unknown", result)

    # -- /event-schema -------------------------------------------

    def test_event_schema_no_args_shows_usage(self):
        result = self._run("event-schema", "")
        self.assertIn("Usage", result)

    def test_event_schema_register(self):
        result = self._run("event-schema", 'register user.created \'{"name":"str"}\'')
        self.assertIn("Schema registered", result)

    def test_event_schema_list_empty(self):
        result = self._run("event-schema", "list")
        self.assertIn("No schemas", result)

    def test_event_schema_compatible(self):
        result = self._run("event-schema", "compatible 1.0.0 1.1.0")
        self.assertIn("Compatible: True", result)

    def test_event_schema_unknown_subcmd(self):
        result = self._run("event-schema", "foobar")
        self.assertIn("Unknown", result)

    # -- all 4 commands registered -------------------------------

    def test_all_commands_registered(self):
        expected = {"webhook-server", "webhook-send", "event-route", "event-schema"}
        self.assertEqual(set(self.registry.commands.keys()), expected)


if __name__ == "__main__":
    unittest.main()
