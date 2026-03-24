"""Tests for FlowEngine + FlowCheckpointManager — T445."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from lidco.flows.engine import Flow, FlowEngine, FlowResult, FlowStep, StepStatus
from lidco.flows.checkpoint import Checkpoint, FlowCheckpointManager
from lidco.flows.rollback import rollback_to_step


class TestFlowEngine:
    def test_plan_creates_flow(self):
        engine = FlowEngine()
        flow = engine.plan("fix the bug", ["step1", "step2"])
        assert len(flow.steps) == 2
        assert flow.goal == "fix the bug"

    def test_plan_no_steps_creates_single_step(self):
        engine = FlowEngine()
        flow = engine.plan("do something")
        assert len(flow.steps) == 1
        assert flow.steps[0].description == "do something"

    def test_execute_all_steps(self):
        engine = FlowEngine()
        flow = engine.plan("goal", ["a", "b", "c"])
        result = engine.execute(flow)
        assert result.success
        assert result.completed_steps == 3

    def test_execute_with_executor(self):
        engine = FlowEngine()
        executed = []

        def exec_fn(step):
            executed.append(step.name)
            return f"done:{step.name}"

        engine.set_executor(exec_fn)
        flow = engine.plan("goal", ["a", "b"])
        engine.execute(flow)
        assert executed == ["a", "b"]

    def test_execute_step_failure_pauses(self):
        engine = FlowEngine()

        def fail_fn(step):
            raise RuntimeError("boom")

        engine.set_executor(fail_fn)
        flow = engine.plan("goal", ["a", "b"])
        result = engine.execute(flow)
        assert not result.success
        assert result.failed_step is not None
        assert result.failed_step.status == StepStatus.FAILED

    def test_pause_stops_execution(self):
        engine = FlowEngine()

        call_count = {"n": 0}

        def exec_fn(step):
            call_count["n"] += 1
            if call_count["n"] == 1:
                engine.pause()
            return "ok"

        engine.set_executor(exec_fn)
        flow = engine.plan("goal", ["a", "b", "c"])
        result = engine.execute(flow)
        # Only first step executes before pause takes effect for subsequent steps
        assert call_count["n"] == 1

    def test_resume_clears_pause(self):
        engine = FlowEngine()
        engine.pause()
        assert engine.is_paused
        engine.resume()
        assert not engine.is_paused

    def test_status_no_flow(self):
        engine = FlowEngine()
        s = engine.status()
        assert not s["active"]

    def test_status_with_flow(self):
        engine = FlowEngine()
        engine.plan("goal", ["a", "b"])
        s = engine.status()
        assert s["active"]
        assert s["goal"] == "goal"
        assert len(s["steps"]) == 2

    def test_skip_step(self):
        engine = FlowEngine()
        flow = engine.plan("goal", ["a", "b"])
        flow.steps[0].status = StepStatus.PAUSED
        result = engine.skip_step(0)
        assert result
        assert flow.steps[0].status == StepStatus.SKIPPED

    def test_skip_nonexistent_step(self):
        engine = FlowEngine()
        engine.plan("goal", ["a"])
        assert not engine.skip_step(99)

    def test_current_flow_stored(self):
        engine = FlowEngine()
        flow = engine.plan("test")
        assert engine.current_flow is flow

    def test_all_steps_done_on_success(self):
        engine = FlowEngine()
        flow = engine.plan("goal", ["a", "b"])
        engine.execute(flow)
        for s in flow.steps:
            assert s.status == StepStatus.DONE


class TestFlowCheckpointManager:
    def test_save_checkpoint(self, tmp_path):
        (tmp_path / "file.py").write_text("original")
        mgr = FlowCheckpointManager(project_dir=tmp_path)
        cp = mgr.save(0, "step0", ["file.py"])
        assert cp.step_index == 0
        assert cp.files["file.py"] == "original"

    def test_rollback_restores_file(self, tmp_path):
        f = tmp_path / "file.py"
        f.write_text("original")
        mgr = FlowCheckpointManager(project_dir=tmp_path)
        cp = mgr.save(0, "step0", ["file.py"])
        f.write_text("modified")
        assert f.read_text() == "modified"
        mgr.rollback(cp.id)
        assert f.read_text() == "original"

    def test_rollback_unknown_id(self, tmp_path):
        mgr = FlowCheckpointManager(project_dir=tmp_path)
        assert not mgr.rollback("nonexistent")

    def test_list_checkpoints_sorted(self, tmp_path):
        mgr = FlowCheckpointManager(project_dir=tmp_path)
        mgr.save(0, "s0", [])
        mgr.save(1, "s1", [])
        mgr.save(2, "s2", [])
        cps = mgr.list()
        indices = [c.step_index for c in cps]
        assert indices == sorted(indices)

    def test_get_checkpoint(self, tmp_path):
        mgr = FlowCheckpointManager(project_dir=tmp_path)
        cp = mgr.save(0, "s0", [])
        assert mgr.get(cp.id) == cp

    def test_get_unknown(self, tmp_path):
        mgr = FlowCheckpointManager(project_dir=tmp_path)
        assert mgr.get("nope") is None

    def test_missing_file_stored_as_empty(self, tmp_path):
        mgr = FlowCheckpointManager(project_dir=tmp_path)
        cp = mgr.save(0, "s0", ["missing.py"])
        assert cp.files["missing.py"] == ""


class TestRollback:
    def test_rollback_to_step(self, tmp_path):
        f = tmp_path / "x.py"
        f.write_text("v1")
        mgr = FlowCheckpointManager(project_dir=tmp_path)
        flow = Flow(goal="g", steps=[FlowStep(0, "s0", "s0"), FlowStep(1, "s1", "s1")])

        # Save checkpoint for step 0
        cp = mgr.save(0, "s0", ["x.py"])
        flow.steps[0].checkpoint_id = cp.id
        flow.steps[0].status = StepStatus.DONE
        flow.steps[1].status = StepStatus.DONE

        f.write_text("v2")
        ok = rollback_to_step(flow, 0, mgr)
        assert ok
        assert f.read_text() == "v1"
        assert flow.steps[0].status == StepStatus.PENDING
        assert flow.steps[1].status == StepStatus.PENDING

    def test_rollback_no_checkpoint(self, tmp_path):
        flow = Flow(goal="g", steps=[FlowStep(0, "s0", "s0")])
        mgr = FlowCheckpointManager(project_dir=tmp_path)
        assert not rollback_to_step(flow, 0, mgr)

    def test_rollback_unknown_step(self, tmp_path):
        flow = Flow(goal="g", steps=[])
        mgr = FlowCheckpointManager(project_dir=tmp_path)
        assert not rollback_to_step(flow, 5, mgr)
