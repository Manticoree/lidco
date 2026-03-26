"""Tests for T626 Q98 CLI commands."""
import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest


def _make_registry():
    registry = MagicMock()
    registered = {}

    def register_async(name, desc, handler):
        registered[name] = handler

    registry.register_async.side_effect = register_async
    registry._handlers = registered
    return registry


def _get(registry, name):
    return registry._handlers[name]


class TestRegisterQ98:
    def test_all_commands_registered(self):
        from lidco.cli.commands.q98_cmds import register_q98_commands
        r = _make_registry()
        register_q98_commands(r)
        assert "secrets" in r._handlers
        assert "notify" in r._handlers
        assert "scheduler" in r._handlers
        assert "data-pipeline" in r._handlers


# ---------------------------------------------------------------------------
# /secrets
# ---------------------------------------------------------------------------

class TestSecretsCommand:
    def _register(self):
        from lidco.cli.commands.q98_cmds import register_q98_commands
        r = _make_registry()
        register_q98_commands(r)
        return _get(r, "secrets")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_set_and_get(self):
        handler = self._register()
        with patch("lidco.security.secrets_manager.SecretsManager.set"), \
             patch("lidco.security.secrets_manager.SecretsManager.get", return_value="myvalue"):
            asyncio.run(handler("set KEY myvalue"))
            result = asyncio.run(handler("get KEY"))
        assert "KEY" in result or "myvalue" in result

    def test_set_success_message(self):
        handler = self._register()
        with patch("lidco.security.secrets_manager.SecretsManager.set"):
            result = asyncio.run(handler("set MY_SECRET s3cr3t"))
        assert "stored" in result.lower() or "MY_SECRET" in result

    def test_get_missing_key(self):
        handler = self._register()
        with patch("lidco.security.secrets_manager.SecretsManager.get", return_value=None):
            result = asyncio.run(handler("get NONEXISTENT"))
        assert "not found" in result.lower()

    def test_delete_existing(self):
        handler = self._register()
        with patch("lidco.security.secrets_manager.SecretsManager.delete", return_value=True):
            result = asyncio.run(handler("delete MY_KEY"))
        assert "deleted" in result.lower() or "MY_KEY" in result

    def test_delete_missing(self):
        handler = self._register()
        with patch("lidco.security.secrets_manager.SecretsManager.delete", return_value=False):
            result = asyncio.run(handler("delete NO_KEY"))
        assert "not found" in result.lower()

    def test_list_keys(self):
        handler = self._register()
        with patch("lidco.security.secrets_manager.SecretsManager.list", return_value=["A", "B"]):
            result = asyncio.run(handler("list"))
        assert "A" in result and "B" in result

    def test_list_empty(self):
        handler = self._register()
        with patch("lidco.security.secrets_manager.SecretsManager.list", return_value=[]):
            result = asyncio.run(handler("list"))
        assert "No secrets" in result

    def test_export(self):
        handler = self._register()
        with patch("lidco.security.secrets_manager.SecretsManager.export_env", return_value={"KEY": "val"}):
            result = asyncio.run(handler("export"))
        assert "KEY=val" in result

    def test_unknown_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("unknowncmd"))
        assert "Unknown" in result or "unknown" in result.lower()


# ---------------------------------------------------------------------------
# /notify
# ---------------------------------------------------------------------------

class TestNotifyCommand:
    def _register(self):
        from lidco.cli.commands.q98_cmds import register_q98_commands
        r = _make_registry()
        register_q98_commands(r)
        return _get(r, "notify")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_send_basic(self):
        handler = self._register()
        from lidco.notifications.center import Notification
        mock_n = Notification(title="T", body="B", level="info", channels=["log"])
        with patch("lidco.notifications.center.NotificationCenter.send", return_value=mock_n):
            result = asyncio.run(handler("send 'Test Title' 'Test body'"))
        assert "sent" in result.lower() or "log" in result

    def test_send_with_level(self):
        handler = self._register()
        from lidco.notifications.center import Notification
        mock_n = Notification(title="T", body="B", level="warning", channels=["log"])
        with patch("lidco.notifications.center.NotificationCenter.send", return_value=mock_n) as mock_send:
            asyncio.run(handler("send 'Alert' 'Something' --level warning"))
        _, kwargs = mock_send.call_args
        assert kwargs.get("level") == "warning"

    def test_send_missing_args(self):
        handler = self._register()
        result = asyncio.run(handler("send OnlyTitle"))
        assert "Error" in result or "Usage" in result

    def test_webhook_add(self):
        handler = self._register()
        with patch("lidco.notifications.center.NotificationCenter.add_webhook") as mock_add:
            result = asyncio.run(handler("webhook add http://x.com/hook"))
        assert "added" in result.lower() or "http://x.com/hook" in result

    def test_webhook_remove(self):
        handler = self._register()
        with patch("lidco.notifications.center.NotificationCenter.remove_webhook", return_value=True):
            result = asyncio.run(handler("webhook remove http://x.com/hook"))
        assert "removed" in result.lower()

    def test_history_empty(self):
        handler = self._register()
        with patch("lidco.notifications.center.NotificationCenter.get_history", return_value=[]):
            result = asyncio.run(handler("history"))
        assert "No notifications" in result

    def test_clear(self):
        handler = self._register()
        with patch("lidco.notifications.center.NotificationCenter.clear_history", return_value=3):
            result = asyncio.run(handler("clear"))
        assert "3" in result or "Cleared" in result


# ---------------------------------------------------------------------------
# /scheduler
# ---------------------------------------------------------------------------

class TestSchedulerCommand:
    def _register(self):
        from lidco.cli.commands.q98_cmds import register_q98_commands
        r = _make_registry()
        register_q98_commands(r)
        return _get(r, "scheduler")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_add_task(self):
        handler = self._register()
        from lidco.scheduler.task_scheduler import ScheduledTask
        import time
        mock_task = ScheduledTask(
            id="abc123", name="my_task", command="echo hi",
            schedule="every 5m", next_run=time.time() + 300,
        )
        with patch("lidco.scheduler.task_scheduler.TaskScheduler.add", return_value=mock_task):
            result = asyncio.run(handler("add my_task 'echo hi' --schedule 'every 5m'"))
        assert "my_task" in result or "added" in result.lower()

    def test_add_missing_schedule(self):
        handler = self._register()
        result = asyncio.run(handler("add task_name 'echo x'"))
        assert "Error" in result or "--schedule" in result

    def test_remove_task(self):
        handler = self._register()
        with patch("lidco.scheduler.task_scheduler.TaskScheduler.remove", return_value=True):
            result = asyncio.run(handler("remove abc123"))
        assert "removed" in result.lower() or "abc123" in result

    def test_list_empty(self):
        handler = self._register()
        with patch("lidco.scheduler.task_scheduler.TaskScheduler.list", return_value=[]):
            result = asyncio.run(handler("list"))
        assert "No scheduled" in result

    def test_run_no_due(self):
        handler = self._register()
        with patch("lidco.scheduler.task_scheduler.TaskScheduler.run_due", return_value=[]):
            result = asyncio.run(handler("run"))
        assert "No due" in result

    def test_unknown_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("badcmd"))
        assert "Unknown" in result or "unknown" in result.lower()


# ---------------------------------------------------------------------------
# /data-pipeline
# ---------------------------------------------------------------------------

class TestDataPipelineCommand:
    def _register(self):
        from lidco.cli.commands.q98_cmds import register_q98_commands
        r = _make_registry()
        register_q98_commands(r)
        return _get(r, "data-pipeline")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_steps_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("steps"))
        assert "FilterStep" in result
        assert "MapStep" in result

    def test_run_json_file(self, tmp_path):
        data_file = tmp_path / "data.json"
        data_file.write_text(json.dumps([3, 1, 2, 1]))
        handler = self._register()
        result = asyncio.run(handler(f"run {data_file.as_posix()} --unique --limit 3"))
        assert "item" in result.lower()

    def test_run_no_steps(self, tmp_path):
        data_file = tmp_path / "data.json"
        data_file.write_text(json.dumps([1, 2, 3]))
        handler = self._register()
        result = asyncio.run(handler(f"run {data_file.as_posix()}"))
        # Should show item count
        assert "3" in result or "item" in result.lower()

    def test_run_file_not_found(self):
        handler = self._register()
        result = asyncio.run(handler("run /nonexistent/path.json"))
        assert "Error" in result or "not found" in result.lower()

    def test_run_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json {")
        handler = self._register()
        result = asyncio.run(handler(f"run {bad_file.as_posix()}"))
        assert "Error" in result

    def test_run_non_array_json(self, tmp_path):
        obj_file = tmp_path / "obj.json"
        obj_file.write_text(json.dumps({"key": "value"}))
        handler = self._register()
        result = asyncio.run(handler(f"run {obj_file.as_posix()}"))
        assert "array" in result.lower() or "Error" in result

    def test_run_with_limit(self, tmp_path):
        data_file = tmp_path / "data.json"
        data_file.write_text(json.dumps(list(range(20))))
        handler = self._register()
        result = asyncio.run(handler(f"run {data_file.as_posix()} --limit 5"))
        assert "5 item" in result or "5" in result

    def test_unknown_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("badcmd"))
        assert "Unknown" in result or "unknown" in result.lower()
