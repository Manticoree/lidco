"""Tests for src/lidco/workflow/engine.py."""
import pytest

from lidco.workflow.engine import (
    StepStatus,
    WorkflowEngine,
    WorkflowError,
    WorkflowResult,
    WorkflowStep,
)


def _noop(ctx, **_):
    return "ok"

def _fail(ctx, **_):
    raise RuntimeError("step failed")

def _double(ctx, value=None, **_):
    return (value or 0) * 2


class TestWorkflowStep:
    def test_should_run_no_condition(self):
        step = WorkflowStep("s", _noop)
        assert step.should_run({}) is True

    def test_should_run_condition_true(self):
        step = WorkflowStep("s", _noop, condition=lambda ctx: True)
        assert step.should_run({}) is True

    def test_should_run_condition_false(self):
        step = WorkflowStep("s", _noop, condition=lambda ctx: False)
        assert step.should_run({}) is False

    def test_resolve_inputs_empty(self):
        step = WorkflowStep("s", _noop)
        assert step.resolve_inputs({"x": 1}) == {}

    def test_resolve_inputs_maps_context(self):
        step = WorkflowStep("s", _noop, inputs={"value": "x"})
        resolved = step.resolve_inputs({"x": 42})
        assert resolved == {"value": 42}

    def test_resolve_inputs_missing_key_gives_none(self):
        step = WorkflowStep("s", _noop, inputs={"v": "missing"})
        resolved = step.resolve_inputs({})
        assert resolved == {"v": None}


class TestWorkflowResult:
    def test_success_all_ok(self):
        from lidco.workflow.engine import StepResult
        result = WorkflowResult("wf")
        result.steps.append(StepResult("a", StepStatus.SUCCESS))
        result.steps.append(StepResult("b", StepStatus.SUCCESS))
        assert result.success is True

    def test_success_with_skip(self):
        from lidco.workflow.engine import StepResult
        result = WorkflowResult("wf")
        result.steps.append(StepResult("a", StepStatus.SUCCESS))
        result.steps.append(StepResult("b", StepStatus.SKIPPED))
        assert result.success is True

    def test_success_false_on_failure(self):
        from lidco.workflow.engine import StepResult
        result = WorkflowResult("wf")
        result.steps.append(StepResult("a", StepStatus.FAILED))
        assert result.success is False

    def test_failed_steps(self):
        from lidco.workflow.engine import StepResult
        result = WorkflowResult("wf")
        result.steps.append(StepResult("ok", StepStatus.SUCCESS))
        result.steps.append(StepResult("bad", StepStatus.FAILED))
        assert len(result.failed_steps) == 1
        assert result.failed_steps[0].name == "bad"

    def test_summary_contains_name(self):
        result = WorkflowResult("my-pipeline")
        result.finished_at = result.started_at
        assert "my-pipeline" in result.summary()


class TestWorkflowEngine:
    def test_define_and_list(self):
        engine = WorkflowEngine()
        engine.define("pipe", [WorkflowStep("s", _noop)])
        assert "pipe" in engine.list_workflows()

    def test_define_empty_name_raises(self):
        engine = WorkflowEngine()
        with pytest.raises(WorkflowError):
            engine.define("  ", [])

    def test_run_unknown_workflow_raises(self):
        engine = WorkflowEngine()
        with pytest.raises(WorkflowError):
            engine.run("ghost")

    def test_run_success(self):
        engine = WorkflowEngine()
        engine.define("w", [WorkflowStep("step1", _noop)])
        result = engine.run("w")
        assert result.success is True
        assert result.steps[0].name == "step1"

    def test_run_step_output_key(self):
        engine = WorkflowEngine()
        def make_value(ctx, **_):
            return 42
        engine.define("w", [
            WorkflowStep("produce", make_value, output_key="answer")
        ])
        result = engine.run("w")
        assert result.context.get("answer") == 42

    def test_run_step_with_inputs(self):
        engine = WorkflowEngine()
        engine.define("w", [
            WorkflowStep("produce", lambda ctx, **_: 7, output_key="val"),
            WorkflowStep("consume", _double, inputs={"value": "val"}, output_key="result"),
        ])
        result = engine.run("w")
        assert result.context.get("result") == 14

    def test_run_failed_step_stops(self):
        engine = WorkflowEngine()
        engine.define("w", [
            WorkflowStep("bad", _fail),
            WorkflowStep("never", _noop),
        ])
        result = engine.run("w", stop_on_first_failure=True)
        assert result.success is False
        assert len(result.steps) == 1

    def test_run_failed_step_continue(self):
        engine = WorkflowEngine()
        engine.define("w", [
            WorkflowStep("bad", _fail),
            WorkflowStep("ok", _noop),
        ])
        result = engine.run("w", stop_on_first_failure=False)
        assert len(result.steps) == 2

    def test_step_on_error_skip(self):
        engine = WorkflowEngine()
        engine.define("w", [WorkflowStep("s", _fail, on_error="skip")])
        result = engine.run("w")
        assert result.steps[0].status == StepStatus.SKIPPED

    def test_step_condition_skip(self):
        engine = WorkflowEngine()
        engine.define("w", [
            WorkflowStep("s", _noop, condition=lambda ctx: False)
        ])
        result = engine.run("w")
        assert result.steps[0].status == StepStatus.SKIPPED
        assert result.success is True

    def test_step_decorator(self):
        engine = WorkflowEngine()

        @engine.step("decorated", output_key="out")
        def my_step(ctx, **_):
            return "decorated_output"

        assert "__default__" in engine.list_workflows()

    def test_run_default_workflow(self):
        engine = WorkflowEngine()

        @engine.step("s1")
        def step_one(ctx, **_):
            return "done"

        result = engine.run()
        assert result.success is True

    def test_add_step(self):
        engine = WorkflowEngine()
        engine.add_step("wf", WorkflowStep("s", _noop))
        assert "wf" in engine.list_workflows()

    def test_initial_context_passed(self):
        engine = WorkflowEngine()
        captured = {}

        def capture(ctx, **_):
            captured.update(ctx)
            return None

        engine.define("w", [WorkflowStep("c", capture)])
        engine.run("w", initial_context={"key": "value"})
        assert captured.get("key") == "value"

    def test_duration_ms_positive(self):
        engine = WorkflowEngine()
        engine.define("w", [WorkflowStep("s", _noop)])
        result = engine.run("w")
        assert result.duration_ms >= 0
