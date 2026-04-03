"""Tests for lidco.notify.dispatcher."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from lidco.notify.dispatcher import Notification, NotificationDispatcher


class TestNotification(unittest.TestCase):
    def test_frozen_dataclass(self):
        n = Notification(id="abc", title="T", message="M")
        self.assertEqual(n.level, "info")
        self.assertFalse(n.delivered)
        with self.assertRaises(AttributeError):
            n.title = "X"  # type: ignore[misc]


class TestNotificationDispatcher(unittest.TestCase):
    def test_send_returns_notification(self):
        d = NotificationDispatcher()
        n = d.send("Hello", "World")
        self.assertEqual(n.title, "Hello")
        self.assertEqual(n.message, "World")
        self.assertEqual(n.level, "info")
        self.assertTrue(n.delivered)

    def test_send_custom_level(self):
        d = NotificationDispatcher()
        n = d.send("E", "err", level="error")
        self.assertEqual(n.level, "error")

    def test_disable_prevents_delivery(self):
        d = NotificationDispatcher()
        d.disable()
        n = d.send("T", "M")
        self.assertFalse(n.delivered)

    def test_enable_after_disable(self):
        d = NotificationDispatcher(enabled=False)
        self.assertFalse(d.is_enabled())
        d.enable()
        self.assertTrue(d.is_enabled())
        n = d.send("T", "M")
        self.assertTrue(n.delivered)

    def test_history_tracks_sends(self):
        d = NotificationDispatcher()
        d.send("A", "a")
        d.send("B", "b")
        self.assertEqual(len(d.history()), 2)

    @patch("lidco.notify.dispatcher.sys")
    def test_detect_platform_windows(self, mock_sys):
        mock_sys.platform = "win32"
        d = NotificationDispatcher.__new__(NotificationDispatcher)
        self.assertEqual(d._detect_platform(), "windows")

    @patch("lidco.notify.dispatcher.sys")
    def test_detect_platform_macos(self, mock_sys):
        mock_sys.platform = "darwin"
        d = NotificationDispatcher.__new__(NotificationDispatcher)
        self.assertEqual(d._detect_platform(), "macos")

    @patch("lidco.notify.dispatcher.sys")
    def test_detect_platform_linux(self, mock_sys):
        mock_sys.platform = "linux"
        d = NotificationDispatcher.__new__(NotificationDispatcher)
        self.assertEqual(d._detect_platform(), "linux")

    @patch("lidco.notify.dispatcher.sys")
    def test_detect_platform_unknown(self, mock_sys):
        mock_sys.platform = "freebsd"
        d = NotificationDispatcher.__new__(NotificationDispatcher)
        self.assertEqual(d._detect_platform(), "unknown")

    def test_summary(self):
        d = NotificationDispatcher()
        d.send("T", "M")
        s = d.summary()
        self.assertEqual(s["total"], 1)
        self.assertEqual(s["delivered"], 1)
        self.assertTrue(s["enabled"])

    def test_explicit_platform(self):
        d = NotificationDispatcher(platform="macos")
        self.assertEqual(d._platform, "macos")


if __name__ == "__main__":
    unittest.main()
