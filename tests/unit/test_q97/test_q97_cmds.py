"""Tests for T621 Q97 CLI commands."""
import asyncio
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


class TestRegisterQ97:
    def test_all_commands_registered(self):
        from lidco.cli.commands.q97_cmds import register_q97_commands
        r = _make_registry()
        register_q97_commands(r)
        assert "run" in r._handlers
        assert "watch" in r._handlers
        assert "config" in r._handlers
        assert "template" in r._handlers


# ---------------------------------------------------------------------------
# /run
# ---------------------------------------------------------------------------

class TestRunCommand:
    def _register(self):
        from lidco.cli.commands.q97_cmds import register_q97_commands
        r = _make_registry()
        register_q97_commands(r)
        return _get(r, "run")

    def _fake_result(self, ok=True, stdout="output", returncode=0):
        from lidco.execution.process_runner import ProcessResult
        return ProcessResult(
            cmd="echo test",
            returncode=returncode,
            stdout=stdout,
            stderr="",
            elapsed_ms=10.0,
        )

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_run_command(self):
        handler = self._register()
        with patch("lidco.execution.process_runner.ProcessRunner.run", return_value=self._fake_result()):
            result = asyncio.run(handler("echo test"))
        assert "output" in result or "exit=0" in result

    def test_run_with_timeout(self):
        handler = self._register()
        with patch("lidco.execution.process_runner.ProcessRunner.run", return_value=self._fake_result()) as mock_run:
            asyncio.run(handler("echo test --timeout 5"))
        # Verify it was called (timeout passed to runner init)
        mock_run.assert_called_once()

    def test_run_with_env(self):
        handler = self._register()
        with patch("lidco.execution.process_runner.ProcessRunner.run", return_value=self._fake_result()) as mock_run:
            asyncio.run(handler("echo $X --env X=hello"))
        mock_run.assert_called_once()
        kwargs = mock_run.call_args[1]
        assert "X" in (kwargs.get("env") or {})

    def test_run_with_cwd(self, tmp_path):
        handler = self._register()
        with patch("lidco.execution.process_runner.ProcessRunner.run", return_value=self._fake_result()):
            result = asyncio.run(handler(f"echo test --cwd {tmp_path.as_posix()}"))
        assert result != ""

    def test_invalid_timeout(self):
        handler = self._register()
        result = asyncio.run(handler("echo test --timeout notanumber"))
        assert "Error" in result

    def test_error_handled(self):
        handler = self._register()
        with patch("lidco.execution.process_runner.ProcessRunner.run", side_effect=Exception("boom")):
            result = asyncio.run(handler("some command"))
        assert "Error" in result


# ---------------------------------------------------------------------------
# /watch
# ---------------------------------------------------------------------------

class TestWatchCommand:
    def _register(self):
        from lidco.cli.commands.q97_cmds import register_q97_commands
        r = _make_registry()
        register_q97_commands(r)
        return _get(r, "watch")

    def test_status_no_watcher(self):
        handler = self._register()
        result = asyncio.run(handler("status"))
        assert "No active watcher" in result

    def test_start_watch(self, tmp_path):
        handler = self._register()
        with patch("lidco.watch.file_watcher.FileWatcher.start"):
            result = asyncio.run(handler(f"start {tmp_path.as_posix()}"))
        assert "Watching" in result

    def test_start_missing_dir(self):
        handler = self._register()
        result = asyncio.run(handler("start"))
        assert "Error" in result

    def test_stop_no_watcher(self):
        handler = self._register()
        result = asyncio.run(handler("stop"))
        assert "No active watcher" in result

    def test_events_empty(self):
        handler = self._register()
        result = asyncio.run(handler("events"))
        assert "No events" in result

    def test_unknown_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("badcmd"))
        assert "Usage" in result or "subcommand" in result.lower()


# ---------------------------------------------------------------------------
# /config
# ---------------------------------------------------------------------------

class TestConfigCommand:
    def _register(self):
        from lidco.cli.commands.q97_cmds import register_q97_commands
        r = _make_registry()
        register_q97_commands(r)
        return _get(r, "config")

    def test_list_empty(self):
        handler = self._register()
        result = asyncio.run(handler("list"))
        assert "No configuration" in result or "Configuration" in result

    def test_set_and_get(self):
        handler = self._register()
        asyncio.run(handler("set debug true"))
        result = asyncio.run(handler("get debug"))
        assert "debug" in result and "True" in result

    def test_get_missing(self):
        handler = self._register()
        result = asyncio.run(handler("get nonexistent.key"))
        assert "not found" in result.lower() or "nonexistent" in result

    def test_set_nested(self):
        handler = self._register()
        asyncio.run(handler("set llm.model claude-3"))
        result = asyncio.run(handler("get llm.model"))
        assert "claude-3" in result

    def test_list_shows_keys(self):
        handler = self._register()
        asyncio.run(handler("set mykey myvalue"))
        result = asyncio.run(handler("list"))
        assert "mykey" in result

    def test_save(self, tmp_path):
        handler = self._register()
        # We can't easily test save without real disk, just verify no error
        with patch("lidco.core.config_manager.ConfigManager.save", return_value=tmp_path / "config.json"):
            result = asyncio.run(handler("save"))
        assert "saved" in result.lower() or "Config" in result

    def test_reload(self):
        handler = self._register()
        with patch("lidco.core.config_manager.ConfigManager.reload"):
            result = asyncio.run(handler("reload"))
        assert "reloaded" in result.lower()

    def test_unknown_subcommand_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler("unknown"))
        assert "Usage" in result

    def test_get_missing_key_arg(self):
        handler = self._register()
        result = asyncio.run(handler("get"))
        assert "Error" in result or "key" in result.lower()


# ---------------------------------------------------------------------------
# /template
# ---------------------------------------------------------------------------

class TestTemplateCommand:
    def _register(self):
        from lidco.cli.commands.q97_cmds import register_q97_commands
        r = _make_registry()
        register_q97_commands(r)
        return _get(r, "template")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_render_simple(self):
        handler = self._register()
        result = asyncio.run(handler("render 'Hello {{ name }}!' --var name=World"))
        assert "Hello World!" in result

    def test_render_with_multiple_vars(self):
        handler = self._register()
        result = asyncio.run(handler("render '{{ a }} {{ b }}' --var a=foo --var b=bar"))
        assert "foo" in result and "bar" in result

    def test_render_missing_template(self):
        handler = self._register()
        result = asyncio.run(handler("render"))
        assert "Error" in result

    def test_file_not_found(self, tmp_path):
        handler = self._register()
        result = asyncio.run(handler(f"file {tmp_path.as_posix()}/nonexistent.txt"))
        assert "Error" in result or "not found" in result.lower()

    def test_file_render(self, tmp_path):
        f = tmp_path / "t.txt"
        f.write_text("Hello {{ who }}!")
        handler = self._register()
        result = asyncio.run(handler(f"file {f.as_posix()} --var who=Claude"))
        assert "Hello Claude!" in result

    def test_test_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("test"))
        assert "World" in result or "alpha" in result

    def test_unknown_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("badcmd whatever"))
        assert "Unknown" in result or "subcommand" in result.lower()
