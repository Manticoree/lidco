"""Tests for src/lidco/tools/trace_inspector.py"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.trace_inspector import TraceInspectorTool


class TestTraceInspectorTool:
    def test_name(self):
        tool = TraceInspectorTool()
        assert tool.name == "capture_execution_trace"

    def test_parameters_include_required(self):
        tool = TraceInspectorTool()
        param_names = {p.name for p in tool.parameters}
        assert "test_command" in param_names
        assert "target_file" in param_names

    def test_parameters_optional_have_defaults(self):
        tool = TraceInspectorTool()
        for p in tool.parameters:
            if not p.required:
                assert p.default is not None

    def test_permission_is_ask(self):
        from lidco.tools.base import ToolPermission
        tool = TraceInspectorTool()
        assert tool.permission == ToolPermission.ASK

    def test_description_not_empty(self):
        tool = TraceInspectorTool()
        assert len(tool.description) > 20

    @pytest.mark.asyncio
    async def test_execute_returns_error_on_none_session(self):
        tool = TraceInspectorTool()
        with patch("lidco.core.trace_recorder.record_trace", return_value=None):
            result = await tool.execute(
                test_command="tests/t.py::test",
                target_file="src/foo.py",
            )
        assert not result.success
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_execute_returns_success_with_session(self):
        from lidco.core.trace_recorder import TraceEvent, TraceSession
        fake_session = TraceSession(
            events=[
                TraceEvent("src/foo.py", 10, "line", {"x": "42"}, 0)
            ],
            target_file="src/foo.py",
            target_function="run",
            total_events=1,
            truncated=False,
        )
        with patch("lidco.core.trace_recorder.record_trace", return_value=fake_session), \
             patch("lidco.core.trace_recorder.load_baseline", return_value={}), \
             patch("lidco.core.trace_recorder.detect_anomalies", return_value=[]):
            tool = TraceInspectorTool()
            result = await tool.execute(
                test_command="tests/t.py::test",
                target_file="src/foo.py",
            )
        assert result.success

    @pytest.mark.asyncio
    async def test_save_baseline_calls_save(self):
        from lidco.core.trace_recorder import TraceSession
        fake_session = TraceSession([], "src/foo.py", "", 0, False)
        with patch("lidco.core.trace_recorder.record_trace", return_value=fake_session) as mock_record, \
             patch("lidco.core.trace_recorder.save_baseline") as mock_save:
            tool = TraceInspectorTool()
            result = await tool.execute(
                test_command="tests/t.py::test",
                target_file="src/foo.py",
                save_baseline=True,
            )
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_anomalies_included_in_output(self):
        from lidco.core.trace_recorder import TraceAnomaly, TraceEvent, TraceSession
        fake_session = TraceSession(
            events=[TraceEvent("src/foo.py", 10, "line", {"x": "None"}, 0)],
            target_file="src/foo.py",
            target_function="run",
            total_events=1,
            truncated=False,
        )
        fake_anomaly = TraceAnomaly(
            line=10, variable="x",
            failing_value="None", baseline_value="42",
            anomaly_type="unexpected_none",
        )
        with patch("lidco.core.trace_recorder.record_trace", return_value=fake_session), \
             patch("lidco.core.trace_recorder.load_baseline", return_value={"k": {}}), \
             patch("lidco.core.trace_recorder.detect_anomalies", return_value=[fake_anomaly]):
            tool = TraceInspectorTool()
            result = await tool.execute(
                test_command="tests/t.py::test",
                target_file="src/foo.py",
            )
        assert "Anomalies" in result.output or "unexpected_none" in result.output
