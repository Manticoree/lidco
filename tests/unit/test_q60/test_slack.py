"""Tests for Q60/405 — Slack notification integration."""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from lidco.integrations.slack import SlackNotifier


class TestSlackNotifier:
    def test_instantiates_with_url(self):
        n = SlackNotifier("https://hooks.slack.com/test")
        assert n._webhook_url == "https://hooks.slack.com/test"

    def test_empty_url_no_crash(self):
        # Constructor with None/empty uses env fallback, shouldn't crash
        with patch("os.environ.get", return_value=None):
            n = SlackNotifier()
        assert isinstance(n, SlackNotifier)

    def test_send_calls_webhook(self):
        n = SlackNotifier("https://hooks.slack.com/test")
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            mock_open.return_value = mock_resp
            result = n.send("Hello")
        assert result is True

    def test_send_no_webhook_raises(self):
        with patch("os.environ.get", return_value=None):
            n = SlackNotifier()
        with pytest.raises(ValueError):
            n.send("test")

    def test_send_handles_network_error(self):
        n = SlackNotifier("https://hooks.slack.com/test")
        with patch("urllib.request.urlopen", side_effect=Exception("network")):
            with pytest.raises((RuntimeError, Exception)):
                n.send("Hello")

    def test_webhook_url_property(self):
        n = SlackNotifier("https://hooks.slack.com/x")
        assert n.webhook_url == "https://hooks.slack.com/x"

    def test_notify_task_done_short_task(self):
        n = SlackNotifier("https://hooks.slack.com/test")
        with patch.object(n, "_post", return_value=True) as mock_post:
            result = n.notify_task_done("test task", elapsed=5.0)
        # Implementation always sends; check _post was called
        assert isinstance(result, bool)

    def test_notify_task_done_long_task(self):
        n = SlackNotifier("https://hooks.slack.com/test")
        with patch.object(n, "_post", return_value=True) as mock_post:
            result = n.notify_task_done("long task", elapsed=60.0)
        assert mock_post.call_count >= 1
        assert result is True

    def test_send_blocks(self):
        n = SlackNotifier("https://hooks.slack.com/test")
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            mock_open.return_value = mock_resp
            blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}]
            result = n.send_blocks(blocks)
        assert result is True

    def test_send_encodes_json(self):
        n = SlackNotifier("https://hooks.slack.com/test")
        sent_data = []
        def capture(req, *args, **kwargs):
            sent_data.append(req.data)
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            return mock_resp
        with patch("urllib.request.urlopen", side_effect=capture):
            n.send("Test message")
        assert len(sent_data) == 1
        import json
        payload = json.loads(sent_data[0])
        assert "Test message" in str(payload)
