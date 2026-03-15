"""Q55/372 — Desktop notifications."""
from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestNotifier:
    def test_notify_task_done_skips_short_tasks(self):
        from lidco.cli.notifier import notify_task_done
        with patch("lidco.cli.notifier.notify") as mock_notify:
            notify_task_done("test task", elapsed_seconds=10.0, min_seconds=30.0)
            mock_notify.assert_not_called()

    def test_notify_task_done_fires_for_long_tasks(self):
        from lidco.cli.notifier import notify_task_done
        with patch("lidco.cli.notifier.notify") as mock_notify:
            notify_task_done("test task", elapsed_seconds=60.0, min_seconds=30.0)
            mock_notify.assert_called_once()
            title, message = mock_notify.call_args[0]
            assert "LIDCO" in title
            assert "test task" in message

    def test_notify_silent_on_error(self):
        """notify() should never raise."""
        from lidco.cli.notifier import notify
        with patch("lidco.cli.notifier._SYSTEM", "Windows"):
            with patch("subprocess.run", side_effect=OSError("not found")):
                notify("Test", "Message")  # should not raise

    def test_notify_time_format_minutes(self):
        from lidco.cli.notifier import notify_task_done
        with patch("lidco.cli.notifier.notify") as mock_notify:
            notify_task_done("long task", elapsed_seconds=125.0, min_seconds=30.0)
            _, message = mock_notify.call_args[0]
            assert "2m" in message

    def test_notify_time_format_seconds_only(self):
        from lidco.cli.notifier import notify_task_done
        with patch("lidco.cli.notifier.notify") as mock_notify:
            notify_task_done("quick task", elapsed_seconds=45.0, min_seconds=30.0)
            _, message = mock_notify.call_args[0]
            assert "45s" in message
