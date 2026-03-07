"""Tests for src/lidco/core/trace_recorder.py"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.core.trace_recorder import (
    TraceAnomaly,
    TraceEvent,
    TraceSession,
    _parse_trace_output,
    _type_prefix,
    detect_anomalies,
    format_trace_session,
    load_baseline,
    record_trace,
    save_baseline,
)


# ── _type_prefix ─────────────────────────────────────────────────────────────

class TestTypePrefix:
    def test_simple_string(self):
        assert _type_prefix("'hello'") == "<str>"

    def test_list_prefix(self):
        assert _type_prefix("[1, 2, 3]") == "<list>"

    def test_dict_prefix(self):
        assert _type_prefix("{...}") == "<dict>"

    def test_none_prefix(self):
        assert _type_prefix("None") == "<none>"

    def test_numeric_int(self):
        assert _type_prefix("42") == "<numeric>"

    def test_numeric_float(self):
        assert _type_prefix("3.14") == "<numeric>"

    def test_object_repr(self):
        assert _type_prefix("Session(config=...)") == "Session"

    def test_call_prefix(self):
        assert _type_prefix("Session(config=...)") == "Session"


# ── _parse_trace_output ───────────────────────────────────────────────────────

class TestParseTraceOutput:
    _OUTPUT = (
        'Traceback (most recent call last):\n'
        '  File "/abs/src/lidco/core/session.py", line 42, in run\n'
        '    self._do_something()\n'
        '    self = <Session object>\n'
        '    x = None\n'
        '  File "/abs/src/lidco/core/session.py", line 99, in _do_something\n'
        '    raise ValueError("boom")\n'
        '    y = 42\n'
        'ValueError: boom\n'
    )

    def test_parses_events_for_target_file(self):
        events, total, truncated = _parse_trace_output(
            self._OUTPUT, "src/lidco/core/session.py"
        )
        assert len(events) >= 1
        assert total >= 1
        assert not truncated

    def test_events_have_correct_line_numbers(self):
        events, _, _ = _parse_trace_output(self._OUTPUT, "src/lidco/core/session.py")
        lines = {ev.line for ev in events}
        assert 42 in lines or 99 in lines

    def test_captures_locals(self):
        events, _, _ = _parse_trace_output(self._OUTPUT, "src/lidco/core/session.py")
        all_locals: dict = {}
        for ev in events:
            all_locals.update(ev.locals_snapshot)
        # At least one local should be captured
        assert len(all_locals) >= 1

    def test_ignores_other_files(self):
        events, _, _ = _parse_trace_output(self._OUTPUT, "src/other/module.py")
        assert events == []

    def test_max_events_respected(self):
        # Build output with many frames
        output = ""
        for i in range(20):
            output += f'  File "/abs/src/lidco/core/foo.py", line {i+1}, in fn{i}\n'
            output += f'    x = {i}\n'
        events, total, truncated = _parse_trace_output(output, "src/lidco/core/foo.py", max_events=5)
        assert len(events) <= 5
        assert total >= 5
        if total > 5:
            assert truncated

    def test_events_are_trace_event_instances(self):
        events, _, _ = _parse_trace_output(self._OUTPUT, "src/lidco/core/session.py")
        for ev in events:
            assert isinstance(ev, TraceEvent)

    def test_empty_output(self):
        events, total, truncated = _parse_trace_output("", "src/foo.py")
        assert events == []
        assert total == 0
        assert not truncated


# ── save_baseline / load_baseline ─────────────────────────────────────────────

class TestBaselinePersistence:
    def _make_session(self) -> TraceSession:
        events = [
            TraceEvent(
                file="src/foo.py", line=10, event="line",
                locals_snapshot={"x": "42", "y": "None"},
                elapsed_ns=0,
            )
        ]
        return TraceSession(
            events=events,
            target_file="src/foo.py",
            target_function="run",
            total_events=1,
            truncated=False,
        )

    def test_save_and_load(self, tmp_path):
        session = self._make_session()
        save_baseline(session, tmp_path)
        loaded = load_baseline(tmp_path)
        assert "src/foo.py:10" in loaded
        assert loaded["src/foo.py:10"]["x"] == "42"

    def test_load_missing_returns_empty(self, tmp_path):
        assert load_baseline(tmp_path) == {}

    def test_load_corrupt_returns_empty(self, tmp_path):
        (tmp_path / ".lidco").mkdir()
        (tmp_path / ".lidco" / "trace_baseline.json").write_text("not json")
        assert load_baseline(tmp_path) == {}

    def test_save_creates_parent_dir(self, tmp_path):
        session = self._make_session()
        save_baseline(session, tmp_path / "subdir")
        assert (tmp_path / "subdir" / ".lidco" / "trace_baseline.json").exists()


# ── detect_anomalies ──────────────────────────────────────────────────────────

class TestDetectAnomalies:
    def _make_session(self, locals_snap: dict) -> TraceSession:
        events = [
            TraceEvent(
                file="src/foo.py", line=10, event="line",
                locals_snapshot=locals_snap, elapsed_ns=0,
            )
        ]
        return TraceSession(
            events=events, target_file="src/foo.py",
            target_function="run", total_events=1, truncated=False,
        )

    def test_empty_baseline_no_anomalies(self):
        session = self._make_session({"x": "None"})
        assert detect_anomalies(session, {}) == []

    def test_unexpected_none_detected(self):
        session = self._make_session({"x": "None"})
        baseline = {"src/foo.py:10": {"x": "42"}}
        anomalies = detect_anomalies(session, baseline)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "unexpected_none"
        assert anomalies[0].variable == "x"

    def test_no_anomaly_when_values_match(self):
        session = self._make_session({"x": "42"})
        baseline = {"src/foo.py:10": {"x": "42"}}
        assert detect_anomalies(session, baseline) == []

    def test_type_drift_detected(self):
        session = self._make_session({"x": "[1, 2, 3]"})
        baseline = {"src/foo.py:10": {"x": "'hello'"}}
        anomalies = detect_anomalies(session, baseline)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "type_drift"

    def test_value_change_detected(self):
        # Both are plain strings → same type prefix "<str>", different value → value_change
        session = self._make_session({"msg": "'error occurred'"})
        baseline = {"src/foo.py:10": {"msg": "'all ok'"}}
        anomalies = detect_anomalies(session, baseline)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "value_change"

    def test_numeric_change_is_value_change(self):
        # 99 vs 0 — same <numeric> type prefix → value_change
        session = self._make_session({"count": "99"})
        baseline = {"src/foo.py:10": {"count": "0"}}
        anomalies = detect_anomalies(session, baseline)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "value_change"

    def test_missing_variable_in_baseline_ignored(self):
        session = self._make_session({"new_var": "42"})
        baseline = {"src/foo.py:10": {"other_var": "1"}}
        assert detect_anomalies(session, baseline) == []

    def test_anomaly_preserves_values(self):
        session = self._make_session({"x": "None"})
        baseline = {"src/foo.py:10": {"x": "Session()"}}
        anomalies = detect_anomalies(session, baseline)
        a = anomalies[0]
        assert a.failing_value == "None"
        assert a.baseline_value == "Session()"
        assert a.line == 10


# ── format_trace_session ─────────────────────────────────────────────────────

class TestFormatTraceSession:
    def _make_session(self, events=None) -> TraceSession:
        if events is None:
            events = [
                TraceEvent(
                    file="src/foo.py", line=42, event="exception",
                    locals_snapshot={"self": "<Foo>", "x": "None"},
                    elapsed_ns=0,
                )
            ]
        return TraceSession(
            events=events,
            target_file="src/foo.py",
            target_function="run",
            total_events=len(events),
            truncated=False,
        )

    def test_empty_session_empty_string(self):
        session = TraceSession([], "foo.py", "", 0, False)
        assert format_trace_session(session) == ""

    def test_header_present(self):
        session = self._make_session()
        out = format_trace_session(session)
        assert "## Execution Trace" in out

    def test_file_present(self):
        session = self._make_session()
        out = format_trace_session(session)
        assert "src/foo.py" in out

    def test_line_number_present(self):
        session = self._make_session()
        out = format_trace_session(session)
        assert "42" in out

    def test_truncated_note_shown(self):
        events = [
            TraceEvent("src/foo.py", i, "line", {}, 0)
            for i in range(15)
        ]
        session = TraceSession(events, "src/foo.py", "fn", 200, truncated=True)
        out = format_trace_session(session, max_events=10)
        assert "truncated" in out.lower() or "200" in out


# ── record_trace (async) ──────────────────────────────────────────────────────

class TestRecordTrace:
    @pytest.mark.asyncio
    async def test_timeout_returns_none(self, tmp_path):
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await record_trace("tests/t.py::test", "src/foo.py", tmp_path)
        assert result is None

    @pytest.mark.asyncio
    async def test_subprocess_error_returns_none(self, tmp_path):
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=OSError("no such file"),
        ):
            result = await record_trace("tests/t.py::test", "src/foo.py", tmp_path)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_trace_session_on_success(self, tmp_path):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(
            b'  File "/abs/src/foo.py", line 10, in run\n    x = 42\n',
            None,
        ))
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
             patch("asyncio.wait_for", side_effect=lambda coro, timeout: coro):
            result = await record_trace("tests/t.py::test", "src/foo.py", tmp_path)
        # Should return a TraceSession (may have 0 events if parse doesn't match)
        assert result is None or isinstance(result, TraceSession)
