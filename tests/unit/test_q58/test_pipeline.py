"""Tests for AgentPipeline — Tasks 390 & 393."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.agents.pipeline import (
    AgentPipeline,
    CheckpointResult,
    PipelineResult,
    PipelineStep,
    StepResult,
)

_SIMPLE_YAML = """
steps:
  - name: analyse
    agent: architect
  - name: code
    agent: coder
    input_from: analyse
"""

_PARALLEL_YAML = """
steps:
  - name: a
    agent: coder
    parallel: true
  - name: b
    agent: tester
    parallel: true
"""

_CHECKPOINT_YAML = """
steps:
  - name: analyse
    agent: architect
  - name: review
    type: checkpoint
  - name: implement
    agent: coder
"""

_CONDITION_YAML = """
steps:
  - name: check
    agent: coder
  - name: optional
    agent: tester
    condition: "len(last_output) > 5"
"""


def _make_session(outputs: list[str]) -> MagicMock:
    session = MagicMock()
    session.get_full_context.return_value = ""
    responses = [MagicMock(content=o) for o in outputs]
    session.orchestrator.handle = AsyncMock(side_effect=responses)
    return session


class TestPipelineStep:
    def test_defaults(self):
        s = PipelineStep(name="foo")
        assert s.agent == ""
        assert s.parallel is False
        assert s.type == "step"
        assert s.condition is None
        assert s.input_from is None


class TestAgentPipelineLoad:
    def test_load_simple(self):
        p = AgentPipeline()
        p.load(_SIMPLE_YAML)
        assert len(p.steps) == 2
        assert p.steps[0].name == "analyse"
        assert p.steps[1].input_from == "analyse"

    def test_load_parallel(self):
        p = AgentPipeline()
        p.load(_PARALLEL_YAML)
        assert all(s.parallel for s in p.steps)

    def test_load_invalid_yaml_raises(self):
        p = AgentPipeline()
        with pytest.raises(ValueError, match="YAML"):
            p.load("not: valid: yaml: [")

    def test_load_missing_steps_raises(self):
        p = AgentPipeline()
        with pytest.raises(ValueError, match="steps"):
            p.load("foo: bar")

    def test_load_step_without_name_raises(self):
        p = AgentPipeline()
        with pytest.raises(ValueError, match="name"):
            p.load("steps:\n  - agent: coder")


class TestAgentPipelineRun:
    @pytest.mark.asyncio
    async def test_sequential_pipeline(self):
        session = _make_session(["arch output", "coder output"])
        p = AgentPipeline()
        p.load(_SIMPLE_YAML)
        result = await p.run("do task", session)
        assert result.success is True
        assert len(result.steps) == 2
        assert result.steps[0].output == "arch output"
        assert result.steps[1].output == "coder output"

    @pytest.mark.asyncio
    async def test_parallel_pipeline(self):
        session = _make_session(["coder out", "tester out"])
        p = AgentPipeline()
        p.load(_PARALLEL_YAML)
        result = await p.run("task", session)
        assert result.success is True
        assert len(result.steps) == 2

    @pytest.mark.asyncio
    async def test_checkpoint_pauses_when_confirm_fn_returns_false(self):
        session = _make_session(["arch output"])
        p = AgentPipeline()
        p.load(_CHECKPOINT_YAML)

        async def _reject(step_name: str, results: dict) -> bool:
            return False

        result = await p.run("task", session, confirm_fn=_reject)
        assert result.success is False
        assert result.checkpoint is not None
        assert result.checkpoint.paused is True
        assert result.checkpoint.step_name == "review"

    @pytest.mark.asyncio
    async def test_checkpoint_continues_when_confirm_fn_returns_true(self):
        session = _make_session(["arch output", "coder output"])
        p = AgentPipeline()
        p.load(_CHECKPOINT_YAML)

        async def _accept(step_name: str, results: dict) -> bool:
            return True

        result = await p.run("task", session, confirm_fn=_accept)
        assert result.success is True
        assert result.checkpoint is None

    @pytest.mark.asyncio
    async def test_checkpoint_auto_continues_without_confirm_fn(self):
        session = _make_session(["arch output", "coder output"])
        p = AgentPipeline()
        p.load(_CHECKPOINT_YAML)
        result = await p.run("task", session)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_condition_skips_step_when_false(self):
        # output is "hi" (2 chars < 5) → condition len > 5 → False → skip
        session = _make_session(["hi"])
        p = AgentPipeline()
        p.load(_CONDITION_YAML)
        result = await p.run("task", session)
        assert len(result.steps) == 2
        assert result.steps[1].skipped is True

    @pytest.mark.asyncio
    async def test_condition_runs_step_when_true(self):
        # output long enough
        session = _make_session(["this is a long enough output", "tester done"])
        p = AgentPipeline()
        p.load(_CONDITION_YAML)
        result = await p.run("task", session)
        assert len(result.steps) == 2
        assert not result.steps[1].skipped
        assert result.steps[1].output == "tester done"

    @pytest.mark.asyncio
    async def test_step_failure_stops_pipeline(self):
        session = MagicMock()
        session.get_full_context.return_value = ""
        session.orchestrator.handle = AsyncMock(side_effect=RuntimeError("fail"))
        p = AgentPipeline()
        p.load(_SIMPLE_YAML)
        result = await p.run("task", session)
        assert result.success is False
        assert len(result.steps) >= 1

    @pytest.mark.asyncio
    async def test_empty_pipeline(self):
        session = MagicMock()
        p = AgentPipeline()
        p.load("steps: []")
        result = await p.run("task", session)
        assert result.success is True
        assert result.steps == []


class TestCheckpointResult:
    def test_defaults(self):
        cr = CheckpointResult(step_name="review")
        assert cr.paused is True
        assert cr.step_name == "review"
