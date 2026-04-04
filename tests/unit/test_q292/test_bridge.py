"""Tests for NotificationBridge."""
import unittest
from unittest.mock import MagicMock

from lidco.slack.bridge import NotificationBridge, PendingNotification
from lidco.slack.client import SlackClient


class TestNotificationBridge(unittest.TestCase):

    def _make_bridge(self, **kwargs):
        client = SlackClient()
        return NotificationBridge(client=client, **kwargs)

    def test_notify_sends_message(self):
        bridge = self._make_bridge()
        result = bridge.notify("deploy", "Deploy v1.2 complete")
        self.assertTrue(result)

    def test_notify_empty_event_raises(self):
        bridge = self._make_bridge()
        with self.assertRaises(ValueError):
            bridge.notify("", "msg")

    def test_notify_empty_message_raises(self):
        bridge = self._make_bridge()
        with self.assertRaises(ValueError):
            bridge.notify("deploy", "")

    def test_configure_channel_changes_routing(self):
        bridge = self._make_bridge()
        bridge.configure_channel("error", "alerts")
        self.assertEqual(bridge.get_channel("error"), "alerts")

    def test_default_channel_used_when_no_mapping(self):
        bridge = self._make_bridge(default_channel="fallback")
        self.assertEqual(bridge.get_channel("unknown_event"), "fallback")

    def test_format_rich_output(self):
        result = NotificationBridge.format_rich({"event_type": "test", "message": "hello"})
        self.assertEqual(result, "[TEST] hello")

    def test_pending_empty_initially(self):
        bridge = self._make_bridge()
        self.assertEqual(bridge.pending(), [])

    def test_pending_populated_on_failure(self):
        client = MagicMock(spec=SlackClient)
        client.send_message.side_effect = RuntimeError("rate limit")
        bridge = NotificationBridge(client=client)
        ok = bridge.notify("error", "something broke")
        self.assertFalse(ok)
        pending = bridge.pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].event_type, "error")

    def test_clear_pending(self):
        client = MagicMock(spec=SlackClient)
        client.send_message.side_effect = RuntimeError("fail")
        bridge = NotificationBridge(client=client)
        bridge.notify("x", "y")
        count = bridge.clear_pending()
        self.assertEqual(count, 1)
        self.assertEqual(bridge.pending(), [])

    def test_configure_empty_event_raises(self):
        bridge = self._make_bridge()
        with self.assertRaises(ValueError):
            bridge.configure_channel("", "channel")

    def test_configure_empty_channel_raises(self):
        bridge = self._make_bridge()
        with self.assertRaises(ValueError):
            bridge.configure_channel("event", "")


if __name__ == "__main__":
    unittest.main()
