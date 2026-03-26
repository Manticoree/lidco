"""Tests for T623 NotificationCenter."""
import sys
from unittest.mock import MagicMock, patch

import pytest

from lidco.notifications.center import Notification, NotificationCenter


class TestNotificationCenter:
    def _make(self, **kwargs):
        return NotificationCenter(**kwargs)

    def test_send_log_calls_callback(self):
        calls = []
        nc = NotificationCenter(log_callback=calls.append)
        nc.send("Title", "Body")
        assert len(calls) == 1
        assert "Title" in calls[0]
        assert "Body" in calls[0]

    def test_send_records_history(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        nc.send("A", "body1")
        nc.send("B", "body2")
        nc.send("C", "body3")
        history = nc.get_history()
        assert len(history) == 3

    def test_history_newest_first(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        nc.send("first", "b")
        nc.send("second", "b")
        history = nc.get_history()
        assert history[0].title == "second"
        assert history[1].title == "first"

    def test_history_max_limit(self):
        nc = NotificationCenter(max_history=2, log_callback=lambda x: None)
        nc.send("A", "b")
        nc.send("B", "b")
        nc.send("C", "b")
        assert len(nc.get_history()) == 2

    def test_clear_history_returns_count(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        nc.send("A", "b")
        nc.send("B", "b")
        count = nc.clear_history()
        assert count == 2
        assert nc.get_history() == []

    def test_add_webhook(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        nc.add_webhook("http://example.com/hook")
        assert "http://example.com/hook" in nc.list_webhooks()

    def test_remove_existing_webhook(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        nc.add_webhook("http://example.com/hook")
        removed = nc.remove_webhook("http://example.com/hook")
        assert removed is True
        assert nc.list_webhooks() == []

    def test_remove_nonexistent_webhook(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        removed = nc.remove_webhook("http://nothere.com")
        assert removed is False

    def test_send_webhook_called(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        nc.add_webhook("http://example.com/hook")
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            nc.send("Title", "Body", channels=["log", "webhook"])
        mock_open.assert_called_once()

    def test_send_webhook_error_captured(self):
        from urllib.error import URLError
        nc = NotificationCenter(log_callback=lambda x: None)
        nc.add_webhook("http://example.com/hook")
        with patch("urllib.request.urlopen", side_effect=URLError("connection refused")):
            n = nc.send("T", "B", channels=["log", "webhook"])
        assert len(n.errors) == 1
        assert "example.com" in n.errors[0]

    def test_send_desktop_linux(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        with patch("sys.platform", "linux"), patch("subprocess.run") as mock_run:
            nc.send("Title", "Body", channels=["desktop"])
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "notify-send"

    def test_send_desktop_macos(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        with patch("sys.platform", "darwin"), patch("subprocess.run") as mock_run:
            nc.send("Title", "Body", channels=["desktop"])
        call_args = mock_run.call_args[0][0]
        assert "osascript" in call_args

    def test_send_desktop_error_captured(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        with patch("sys.platform", "linux"), patch("subprocess.run", side_effect=OSError("no notify-send")):
            n = nc.send("T", "B", channels=["desktop"])
        assert len(n.errors) == 1
        assert "desktop" in n.errors[0]

    def test_invalid_level_raises(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        with pytest.raises(ValueError, match="Invalid level"):
            nc.send("T", "B", level="critical")

    def test_notification_channels_recorded(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        n = nc.send("T", "B", channels=["log"])
        assert n.channels == ["log"]

    def test_auto_includes_webhook_channel(self):
        nc = NotificationCenter(log_callback=lambda x: None)
        nc.add_webhook("http://x.com")
        with patch("urllib.request.urlopen"):
            n = nc.send("T", "B")  # channels=None
        assert "webhook" in n.channels
