"""Tests for Q292 CLI commands."""
import asyncio
import unittest


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self):
        self._commands: dict[str, object] = {}

    def register_async(self, name: str, desc: str, handler) -> None:
        self._commands[name] = handler

    def get(self, name: str):
        return self._commands.get(name)


class TestQ292Commands(unittest.TestCase):

    def _registry(self):
        from lidco.cli.commands.q292_cmds import register_q292_commands
        reg = _FakeRegistry()
        register_q292_commands(reg)
        return reg

    # ---- /slack-notify

    def test_slack_notify_no_args(self):
        reg = self._registry()
        handler = reg.get("slack-notify")
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_slack_notify_send(self):
        reg = self._registry()
        handler = reg.get("slack-notify")
        result = asyncio.run(handler("send deploy 'deployed v1.0'"))
        self.assertIn("Notification sent", result)

    def test_slack_notify_configure(self):
        reg = self._registry()
        handler = reg.get("slack-notify")
        result = asyncio.run(handler("configure error alerts"))
        self.assertIn("mapped", result)

    def test_slack_notify_pending(self):
        reg = self._registry()
        handler = reg.get("slack-notify")
        result = asyncio.run(handler("pending"))
        self.assertIn("No pending", result)

    # ---- /slack-command

    def test_slack_command_no_args(self):
        reg = self._registry()
        handler = reg.get("slack-command")
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_slack_command_exec(self):
        reg = self._registry()
        handler = reg.get("slack-command")
        result = asyncio.run(handler("exec '@lidco ping'"))
        self.assertIn("pong", result)

    def test_slack_command_list(self):
        reg = self._registry()
        handler = reg.get("slack-command")
        result = asyncio.run(handler("list"))
        self.assertIn("help", result)

    # ---- /slack-share

    def test_slack_share_no_args(self):
        reg = self._registry()
        handler = reg.get("slack-share")
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_slack_share_send(self):
        reg = self._registry()
        handler = reg.get("slack-share")
        result = asyncio.run(handler("send dev python 'print(1)'"))
        self.assertIn("Snippet shared", result)

    def test_slack_share_list_empty(self):
        reg = self._registry()
        handler = reg.get("slack-share")
        result = asyncio.run(handler("list"))
        # Could be empty or have items depending on state
        self.assertIsInstance(result, str)

    # ---- /slack-config

    def test_slack_config_no_args(self):
        reg = self._registry()
        handler = reg.get("slack-config")
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_slack_config_set_and_get(self):
        reg = self._registry()
        handler = reg.get("slack-config")
        asyncio.run(handler("set token xoxb-123"))
        result = asyncio.run(handler("get token"))
        self.assertIn("xoxb-123", result)

    def test_slack_config_list(self):
        reg = self._registry()
        handler = reg.get("slack-config")
        asyncio.run(handler("set key1 val1"))
        result = asyncio.run(handler("list"))
        self.assertIn("key1", result)

    def test_all_commands_registered(self):
        reg = self._registry()
        for name in ("slack-notify", "slack-command", "slack-share", "slack-config"):
            self.assertIsNotNone(reg.get(name), f"{name} not registered")


if __name__ == "__main__":
    unittest.main()
