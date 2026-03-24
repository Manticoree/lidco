"""Tests for Task 458: Typed trajectory recorder."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from lidco.trajectory.recorder import (
    Action,
    Observation,
    TrajectoryRecorder,
    TrajectoryStep,
)


class TestTrajectoryRecorder:
    """Tests for TrajectoryRecorder."""

    def _make_step(self, tool: str = "read_file", success: bool = True, elapsed_ms: int = 50) -> tuple[Action, Observation]:
        action = Action(type="tool_call", tool=tool, params={"path": "/tmp/a.py"}, timestamp=time.time())
        obs = Observation(type="tool_result", result="ok", success=success, elapsed_ms=elapsed_ms)
        return action, obs

    def test_record_step(self) -> None:
        rec = TrajectoryRecorder()
        a, o = self._make_step()
        rec.record(a, o)
        assert len(rec.steps) == 1
        assert rec.steps[0].action.tool == "read_file"
        assert rec.steps[0].observation.result == "ok"

    def test_steps_returns_copy(self) -> None:
        rec = TrajectoryRecorder()
        a, o = self._make_step()
        rec.record(a, o)
        steps = rec.steps
        steps.clear()
        assert len(rec.steps) == 1  # original unaffected

    def test_record_tool_event_end(self) -> None:
        rec = TrajectoryRecorder()
        rec.record_tool_event("end", "write_file", {"path": "/a.py"}, "Done", agent="coder", elapsed_ms=100)
        assert len(rec.steps) == 1
        step = rec.steps[0]
        assert step.action.tool == "write_file"
        assert step.action.agent == "coder"
        assert step.observation.success is True
        assert step.observation.elapsed_ms == 100

    def test_record_tool_event_start_ignored(self) -> None:
        rec = TrajectoryRecorder()
        rec.record_tool_event("start", "write_file", {"path": "/a.py"}, None)
        assert len(rec.steps) == 0

    def test_record_tool_event_error_detection(self) -> None:
        rec = TrajectoryRecorder()
        rec.record_tool_event("end", "bash", {}, "Error: command not found")
        assert rec.steps[0].observation.success is False

    def test_truncation_of_large_results(self) -> None:
        rec = TrajectoryRecorder()
        large_result = "x" * 2000
        rec.record_tool_event("end", "read_file", {}, large_result)
        step = rec.steps[0]
        assert step.observation.truncated is True
        assert len(step.observation.result) == 1000

    def test_export_json_creates_file(self, tmp_path: Path) -> None:
        rec = TrajectoryRecorder()
        rec.record_tool_event("end", "bash", {"cmd": "ls"}, "file.py", elapsed_ms=30)
        out = str(tmp_path / "traj.json")
        rec.export_json(out)
        data = json.loads(Path(out).read_text(encoding="utf-8"))
        assert "session_start" in data
        assert len(data["steps"]) == 1
        assert data["steps"][0]["action"]["tool"] == "bash"

    def test_export_jsonl_one_line_per_step(self, tmp_path: Path) -> None:
        rec = TrajectoryRecorder()
        rec.record_tool_event("end", "bash", {}, "ok", elapsed_ms=10)
        rec.record_tool_event("end", "read_file", {}, "content", elapsed_ms=20)
        out = str(tmp_path / "traj.jsonl")
        rec.export_jsonl(out)
        lines = Path(out).read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "action" in parsed
            assert "observation" in parsed

    def test_export_json_roundtrip(self, tmp_path: Path) -> None:
        rec = TrajectoryRecorder()
        rec.record_tool_event("end", "bash", {"cmd": "echo hi"}, "hi", elapsed_ms=5)
        rec.record_tool_event("end", "write_file", {"path": "/a.py"}, "ok", elapsed_ms=15)
        out = str(tmp_path / "roundtrip.json")
        rec.export_json(out)
        data = json.loads(Path(out).read_text(encoding="utf-8"))
        assert isinstance(data["session_start"], float)
        assert len(data["steps"]) == 2
        s0 = data["steps"][0]
        assert s0["action"]["type"] == "tool_call"
        assert s0["observation"]["type"] == "tool_result"

    def test_summary_counts_tools(self) -> None:
        rec = TrajectoryRecorder()
        rec.record_tool_event("end", "bash", {}, "ok", elapsed_ms=10)
        rec.record_tool_event("end", "bash", {}, "ok", elapsed_ms=20)
        rec.record_tool_event("end", "read_file", {}, "ok", elapsed_ms=5)
        s = rec.summary()
        assert s["total_steps"] == 3
        assert s["tool_counts"]["bash"] == 2
        assert s["tool_counts"]["read_file"] == 1
        assert s["total_elapsed_ms"] == 35

    def test_summary_error_count(self) -> None:
        rec = TrajectoryRecorder()
        rec.record_tool_event("end", "bash", {}, "ok", elapsed_ms=10)
        rec.record_tool_event("end", "bash", {}, "Error: fail", elapsed_ms=10)
        s = rec.summary()
        assert s["error_count"] == 1

    def test_empty_trajectory_summary(self) -> None:
        rec = TrajectoryRecorder()
        s = rec.summary()
        assert s["total_steps"] == 0
        assert s["tool_counts"] == {}
        assert s["total_elapsed_ms"] == 0
        assert s["error_count"] == 0

    def test_export_json_creates_parent_dirs(self, tmp_path: Path) -> None:
        rec = TrajectoryRecorder()
        rec.record_tool_event("end", "bash", {}, "ok")
        out = str(tmp_path / "nested" / "dir" / "traj.json")
        rec.export_json(out)
        assert Path(out).exists()

    def test_record_tool_event_none_result(self) -> None:
        rec = TrajectoryRecorder()
        rec.record_tool_event("end", "bash", {}, None)
        step = rec.steps[0]
        assert step.observation.result == ""
        assert step.observation.success is True
