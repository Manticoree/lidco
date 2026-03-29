"""Tests for src/lidco/execution/task_pipeline.py."""
from __future__ import annotations

import asyncio

from lidco.execution.task_pipeline import PipelineResult, PipelineStep, TaskPipeline


def _run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------ #
# PipelineStep                                                         #
# ------------------------------------------------------------------ #

class TestPipelineStep:
    def test_fields(self):
        fn = lambda x: x
        step = PipelineStep(name="s1", fn=fn)
        assert step.name == "s1"
        assert step.fn is fn
        assert step.skip_on_error is False

    def test_skip_on_error_flag(self):
        step = PipelineStep(name="s", fn=lambda x: x, skip_on_error=True)
        assert step.skip_on_error is True


# ------------------------------------------------------------------ #
# PipelineResult                                                       #
# ------------------------------------------------------------------ #

class TestPipelineResult:
    def test_fields(self):
        r = PipelineResult(steps_run=3, steps_skipped=0, final_output="out", errors={}, success=True)
        assert r.steps_run == 3
        assert r.steps_skipped == 0
        assert r.final_output == "out"
        assert r.errors == {}
        assert r.success is True


# ------------------------------------------------------------------ #
# TaskPipeline                                                         #
# ------------------------------------------------------------------ #

class TestTaskPipeline:
    def test_empty_pipeline(self):
        pipeline = TaskPipeline()
        result = pipeline.run("input")
        assert result.steps_run == 0
        assert result.final_output == "input"
        assert result.success is True

    def test_single_step(self):
        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("upper", lambda s: s.upper()))
        result = pipeline.run("hello")
        assert result.final_output == "HELLO"
        assert result.steps_run == 1

    def test_sequential_steps_chain(self):
        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("upper", lambda s: s.upper()))
        pipeline.add_step(PipelineStep("exclaim", lambda s: s + "!"))
        result = pipeline.run("hello")
        assert result.final_output == "HELLO!"
        assert result.steps_run == 2

    def test_error_stops_pipeline_by_default(self):
        calls = []

        def step2(x):
            calls.append("step2")
            return x

        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("bad", lambda x: 1 / 0))
        pipeline.add_step(PipelineStep("good", step2))
        result = pipeline.run("input")
        assert result.success is False
        assert "bad" in result.errors
        assert "step2" not in calls

    def test_skip_on_error_continues(self):
        calls = []

        def step3(x):
            calls.append("step3")
            return "recovered"

        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("bad", lambda x: 1 / 0, skip_on_error=True))
        pipeline.add_step(PipelineStep("good", step3))
        result = pipeline.run("input")
        assert "step3" in calls
        assert result.final_output == "recovered"

    def test_error_captured_in_errors_dict(self):
        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("boom", lambda x: (_ for _ in ()).throw(ValueError("oops"))))
        result = pipeline.run("x")
        assert "boom" in result.errors
        assert "oops" in result.errors["boom"]

    def test_async_step(self):
        async def async_fn(x):
            return x + "_async"

        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("async_step", async_fn))
        result = pipeline.run("hello")
        assert result.final_output == "hello_async"

    def test_mixed_sync_async_steps(self):
        async def async_fn(x):
            return x.upper()

        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("strip", lambda s: s.strip()))
        pipeline.add_step(PipelineStep("upper", async_fn))
        result = pipeline.run("  hello  ")
        assert result.final_output == "HELLO"

    def test_run_async_directly(self):
        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("double", lambda x: x * 2))
        result = _run(pipeline.run_async(5))
        assert result.final_output == 10

    def test_clear_removes_steps(self):
        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("s", lambda x: x))
        pipeline.clear()
        result = pipeline.run("x")
        assert result.steps_run == 0

    def test_steps_run_count(self):
        pipeline = TaskPipeline()
        for i in range(4):
            pipeline.add_step(PipelineStep(f"s{i}", lambda x: x))
        result = pipeline.run("x")
        assert result.steps_run == 4

    def test_steps_skipped_count(self):
        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("bad1", lambda x: 1 / 0, skip_on_error=True))
        pipeline.add_step(PipelineStep("bad2", lambda x: 1 / 0, skip_on_error=True))
        pipeline.add_step(PipelineStep("good", lambda x: "ok"))
        result = pipeline.run("x")
        assert result.steps_skipped == 2

    def test_none_initial_input(self):
        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("check", lambda x: x is None))
        result = pipeline.run(None)
        assert result.final_output is True

    def test_numeric_pipeline(self):
        pipeline = TaskPipeline()
        pipeline.add_step(PipelineStep("add10", lambda x: x + 10))
        pipeline.add_step(PipelineStep("mul2", lambda x: x * 2))
        result = pipeline.run(5)
        assert result.final_output == 30
