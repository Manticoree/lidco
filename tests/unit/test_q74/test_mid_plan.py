"""Tests for mid-execution plan modification — T496."""
from __future__ import annotations
import pytest
from lidco.flows.engine import FlowEngine, StepStatus


class TestMidExecutionPlanModification:
    def test_inject_instruction_returns_true_with_active_flow(self):
        engine = FlowEngine()
        engine.plan("goal", ["step1", "step2"])
        assert engine.inject_instruction("be more careful")

    def test_inject_instruction_returns_false_without_flow(self):
        engine = FlowEngine()
        assert not engine.inject_instruction("instruction")

    def test_pending_instructions_empty_by_default(self):
        engine = FlowEngine()
        assert engine.pending_instructions == []

    def test_pending_instructions_after_inject(self):
        engine = FlowEngine()
        engine.plan("goal", ["step"])
        engine.inject_instruction("do X")
        assert "do X" in engine.pending_instructions

    def test_instructions_applied_to_remaining_steps(self):
        engine = FlowEngine()
        executed = []

        def exec_fn(step):
            executed.append(step.description)
            if len(executed) == 1:
                engine.inject_instruction("be careful")
            return "ok"

        engine.set_executor(exec_fn)
        flow = engine.plan("goal", ["step1", "step2"])
        engine.execute(flow)

        # Second step description should include the injected instruction
        assert len(executed) == 2
        assert "be careful" in executed[1] or "Note" in executed[1]

    def test_instructions_cleared_after_apply(self):
        engine = FlowEngine()
        engine.plan("goal", ["a", "b", "c"])

        call_n = {"n": 0}
        def exec_fn(step):
            call_n["n"] += 1
            if call_n["n"] == 1:
                engine.inject_instruction("hint")
            return "ok"

        engine.set_executor(exec_fn)
        engine.execute(engine.current_flow)
        # After execution, pending instructions should be empty
        assert engine.pending_instructions == []

    def test_multiple_instructions_combined(self):
        engine = FlowEngine()
        engine.plan("goal", ["s1", "s2"])
        engine.inject_instruction("first")
        engine.inject_instruction("second")
        assert len(engine.pending_instructions) == 2
