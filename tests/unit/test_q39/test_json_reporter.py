"""Tests for JSON output formatter — Task 262."""

from __future__ import annotations

import json
import pytest

from lidco.cli.json_reporter import ExecResult, ExecStats, FileChange
from lidco.cli.exit_codes import SUCCESS, TASK_FAILED


class TestFileChange:
    def test_defaults(self):
        fc = FileChange(file="src/foo.py", action="edit")
        assert fc.lines_added == 0
        assert fc.lines_removed == 0


class TestExecResult:
    def _make(self, **kwargs):
        defaults = dict(
            session_id="abc123",
            task="fix tests",
            status="success",
            exit_code=SUCCESS,
            duration_s=1.5,
            cost_usd=0.001,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            tool_calls=3,
            changes=[],
            output="Done",
            error=None,
        )
        defaults.update(kwargs)
        return ExecResult(**defaults)

    def test_to_dict_nests_tokens(self):
        r = self._make()
        d = r.to_dict()
        assert "tokens" in d
        assert d["tokens"]["total"] == 150
        assert d["tokens"]["prompt"] == 100
        assert d["tokens"]["completion"] == 50
        assert "total_tokens" not in d
        assert "prompt_tokens" not in d
        assert "completion_tokens" not in d

    def test_to_json_valid(self):
        r = self._make()
        text = r.to_json()
        parsed = json.loads(text)
        assert parsed["session_id"] == "abc123"
        assert parsed["status"] == "success"
        assert parsed["exit_code"] == 0

    def test_to_json_includes_changes(self):
        r = self._make(changes=[FileChange("src/foo.py", "edit", 5, 2)])
        d = r.to_dict()
        assert len(d["changes"]) == 1
        assert d["changes"][0]["file"] == "src/foo.py"
        assert d["changes"][0]["action"] == "edit"

    def test_error_field_preserved(self):
        r = self._make(status="failed", exit_code=TASK_FAILED, error="something failed")
        d = r.to_dict()
        assert d["error"] == "something failed"

    def test_print_json_writes_to_stdout(self, capsys):
        r = self._make()
        r.print_json()
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["task"] == "fix tests"


class TestExecStats:
    def test_initial_state(self):
        s = ExecStats()
        assert s.total_tokens == 0
        assert s.tool_calls == 0
        assert s.changes == []
        assert s.cost_usd == 0.0

    def test_on_tokens(self):
        s = ExecStats()
        s.on_tokens(500, 0.05)
        assert s.total_tokens == 500
        assert s.cost_usd == 0.05

    def test_on_tool_event_counts_calls(self):
        s = ExecStats()
        s.on_tool_event("tool_start", "bash", {})
        s.on_tool_event("tool_start", "grep", {})
        assert s.tool_calls == 2

    def test_on_tool_event_tracks_file_write(self):
        s = ExecStats()
        s.on_tool_event("tool_end", "file_write", {"path": "src/foo.py"})
        assert len(s.changes) == 1
        assert s.changes[0].file == "src/foo.py"
        assert s.changes[0].action == "write"

    def test_on_tool_event_tracks_file_edit(self):
        s = ExecStats()
        s.on_tool_event("tool_end", "file_edit", {"path": "src/bar.py"})
        assert len(s.changes) == 1
        assert s.changes[0].action == "edit"

    def test_on_tool_event_ignores_other_tools(self):
        s = ExecStats()
        s.on_tool_event("tool_end", "bash", {"command": "pytest"})
        assert s.changes == []

    def test_on_tool_event_ignores_tool_start_for_changes(self):
        s = ExecStats()
        s.on_tool_event("tool_start", "file_write", {"path": "x.py"})
        # Should not track change on start, only on end
        assert s.changes == []

    def test_elapsed_is_positive(self):
        s = ExecStats()
        assert s.elapsed() >= 0.0
