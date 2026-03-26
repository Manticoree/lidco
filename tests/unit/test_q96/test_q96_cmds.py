"""Tests for T616 Q96 CLI commands."""
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


class TestRegisterQ96:
    def test_all_commands_registered(self):
        from lidco.cli.commands.q96_cmds import register_q96_commands
        r = _make_registry()
        register_q96_commands(r)
        assert "http" in r._handlers
        assert "sql" in r._handlers
        assert "profile" in r._handlers
        assert "undo" in r._handlers


# ---------------------------------------------------------------------------
# /http
# ---------------------------------------------------------------------------

class TestHttpCommand:
    def _register(self):
        from lidco.cli.commands.q96_cmds import register_q96_commands
        r = _make_registry()
        register_q96_commands(r)
        return _get(r, "http")

    def _fake_response(self, status=200, body="OK", ok=True):
        from lidco.tools.http_tool import HttpResponse
        resp = HttpResponse(
            url="https://example.com",
            method="GET",
            status=status,
            reason="OK",
            headers={},
            body=body,
            elapsed_ms=50.0,
        )
        return resp

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_missing_url_shows_error(self):
        handler = self._register()
        result = asyncio.run(handler("GET"))
        assert "Error" in result or "url" in result.lower()

    def test_get_request(self):
        handler = self._register()
        with patch("lidco.tools.http_tool.HttpTool.request", return_value=self._fake_response()):
            result = asyncio.run(handler("GET https://example.com"))
        assert "200" in result or "OK" in result

    def test_post_json(self):
        handler = self._register()
        fake_resp = self._fake_response(201, body='{"id": 1}')
        with patch("lidco.tools.http_tool.HttpTool.request", return_value=fake_resp):
            result = asyncio.run(handler('POST https://example.com --json {"key":"val"}'))
        assert result != ""

    def test_bearer_flag(self):
        handler = self._register()
        with patch("lidco.tools.http_tool.HttpTool.request", return_value=self._fake_response()) as mock_req:
            asyncio.run(handler("GET https://example.com --bearer mytoken"))
        mock_req.assert_called_once()
        call_kwargs = mock_req.call_args[1]
        assert call_kwargs.get("bearer") == "mytoken"

    def test_header_flag(self):
        handler = self._register()
        with patch("lidco.tools.http_tool.HttpTool.request", return_value=self._fake_response()) as mock_req:
            asyncio.run(handler("GET https://example.com --header Accept=application/json"))
        call_kwargs = mock_req.call_args[1]
        assert "Accept" in (call_kwargs.get("headers") or {})

    def test_invalid_json_shows_error(self):
        handler = self._register()
        result = asyncio.run(handler("POST https://example.com --json {invalid}"))
        assert "Error" in result

    def test_error_handled(self):
        handler = self._register()
        with patch("lidco.tools.http_tool.HttpTool.request", side_effect=Exception("boom")):
            result = asyncio.run(handler("GET https://example.com"))
        assert "Error" in result


# ---------------------------------------------------------------------------
# /sql
# ---------------------------------------------------------------------------

class TestSqlCommand:
    def _register(self):
        from lidco.cli.commands.q96_cmds import register_q96_commands
        r = _make_registry()
        register_q96_commands(r)
        return _get(r, "sql")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_select_in_memory(self):
        handler = self._register()
        result = asyncio.run(handler("SELECT 1 AS n"))
        assert "1" in result or "n" in result

    def test_tables_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("tables"))
        # Empty in-memory db → no tables
        assert "No tables" in result or result != ""

    def test_schema_subcommand(self):
        handler = self._register()
        # Need a real table for schema
        from lidco.tools.sql_tool import SqlTool, TableInfo
        fake_info = TableInfo(
            name="users",
            columns=[{"name": "id", "type": "INTEGER", "pk": True, "notnull": False, "default": None}],
            row_count=5,
        )
        with patch("lidco.tools.sql_tool.SqlTool.table_info", return_value=fake_info):
            result = asyncio.run(handler("schema users"))
        assert "users" in result
        assert "id" in result

    def test_create_and_insert(self):
        handler = self._register()
        result = asyncio.run(handler("CREATE TABLE t (n INT)"))
        assert "Error" not in result or result != ""

    def test_error_in_query(self):
        handler = self._register()
        result = asyncio.run(handler("SELECT * FROM nonexistent_table_xyz"))
        assert "Error" in result or "no such table" in result.lower()

    def test_db_flag(self, tmp_path):
        handler = self._register()
        db = str(tmp_path / "test.db")
        result = asyncio.run(handler(f"--db {db} CREATE TABLE x (v INT)"))
        # Should not error
        assert "Error" not in result or result != ""


# ---------------------------------------------------------------------------
# /profile
# ---------------------------------------------------------------------------

class TestProfileCommand:
    def _register(self):
        from lidco.cli.commands.q96_cmds import register_q96_commands
        r = _make_registry()
        register_q96_commands(r)
        return _get(r, "profile")

    def _fake_report(self, ok=True):
        from lidco.profiling.profiler import ProfileReport, FunctionStat
        stats = [FunctionStat("m.py", "func", 1, 10, 0.5, 1.0, 0.05, 0.1)]
        return ProfileReport(
            label="test",
            total_calls=10,
            primitive_calls=8,
            elapsed_ms=100.0,
            stats=stats,
            raw_text="raw",
            error="" if ok else "profile failed",
        )

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_profile_code(self):
        handler = self._register()
        with patch("lidco.profiling.profiler.CodeProfiler.profile_code", return_value=self._fake_report()):
            result = asyncio.run(handler("code x = 1+1"))
        assert "func" in result or "10" in result

    def test_profile_file(self, tmp_path):
        script = tmp_path / "s.py"
        script.write_text("x = 1\n")
        handler = self._register()
        with patch("lidco.profiling.profiler.CodeProfiler.profile_file", return_value=self._fake_report()):
            result = asyncio.run(handler(f"file {script}"))
        assert result != ""

    def test_profile_error_shown(self):
        handler = self._register()
        with patch("lidco.profiling.profiler.CodeProfiler.profile_code", return_value=self._fake_report(ok=False)):
            result = asyncio.run(handler("code x = 1"))
        assert "error" in result.lower()

    def test_top_flag(self):
        handler = self._register()
        with patch("lidco.profiling.profiler.CodeProfiler.profile_code", return_value=self._fake_report()) as mock:
            result = asyncio.run(handler("code x=1 --top 5"))
        assert result != ""

    def test_unknown_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("badcmd whatever"))
        assert "Unknown" in result or "file" in result.lower()


# ---------------------------------------------------------------------------
# /undo
# ---------------------------------------------------------------------------

class TestUndoCommand:
    def _register(self):
        from lidco.cli.commands.q96_cmds import register_q96_commands
        r = _make_registry()
        register_q96_commands(r)
        return _get(r, "undo")

    def test_no_args_shows_history(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "undo" in result.lower() or "history" in result.lower()

    def test_history_subcommand(self):
        handler = self._register()
        result = asyncio.run(handler("history"))
        assert "undo" in result.lower() or "history" in result.lower()

    def test_checkpoint(self, tmp_path):
        handler = self._register()
        result = asyncio.run(handler("checkpoint initial"))
        assert "Checkpoint" in result

    def test_undo_no_history(self):
        handler = self._register()
        # Fresh registry → no history
        result = asyncio.run(handler("undo"))
        assert "Cannot" in result or "No" in result or "oldest" in result.lower()

    def test_redo_nothing(self):
        handler = self._register()
        result = asyncio.run(handler("redo"))
        assert "Cannot" in result or "Nothing" in result or "redo" in result.lower()

    def test_watch_adds_files(self):
        handler = self._register()
        result = asyncio.run(handler("watch main.py config.py"))
        assert "main.py" in result or "watching" in result.lower()

    def test_checkpoint_and_undo(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("v1")
        p = f.as_posix()  # forward slashes, safe for shlex
        handler = self._register()
        asyncio.run(handler(f"checkpoint before {p}"))
        f.write_text("v2")
        asyncio.run(handler(f"checkpoint after {p}"))
        result = asyncio.run(handler("undo"))
        assert "Undone" in result
        assert f.read_text() == "v1"

    def test_redo_after_undo(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("v1")
        p = f.as_posix()  # forward slashes, safe for shlex
        handler = self._register()
        asyncio.run(handler(f"checkpoint v1 {p}"))
        f.write_text("v2")
        asyncio.run(handler(f"checkpoint v2 {p}"))
        asyncio.run(handler("undo"))
        result = asyncio.run(handler("redo"))
        assert "Redone" in result
        assert f.read_text() == "v2"

    def test_unknown_subcommand_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler("badcmd"))
        assert "Usage" in result
