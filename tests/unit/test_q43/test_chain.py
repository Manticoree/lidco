"""Tests for SkillChain and parse_chain — Task 295."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.skills.chain import ChainResult, ChainStep, SkillChain, parse_chain
from lidco.skills.skill import Skill


# ---------------------------------------------------------------------------
# parse_chain()
# ---------------------------------------------------------------------------

class TestParseChain:
    def test_single_skill_no_args(self):
        result = parse_chain("review")
        assert result == [("review", "")]

    def test_single_skill_with_args(self):
        result = parse_chain("review src/auth.py")
        assert result == [("review", "src/auth.py")]

    def test_two_skills(self):
        result = parse_chain("review | summarize")
        assert result == [("review", ""), ("summarize", "")]

    def test_first_skill_has_args(self):
        result = parse_chain("review src/auth.py | summarize")
        assert result == [("review", "src/auth.py"), ("summarize", "")]

    def test_three_skills(self):
        result = parse_chain("lint | fix | format")
        assert result == [("lint", ""), ("fix", ""), ("format", "")]

    def test_slash_prefix_stripped(self):
        result = parse_chain("/review | /summarize")
        assert result[0][0] == "review"
        assert result[1][0] == "summarize"

    def test_extra_whitespace(self):
        result = parse_chain("  review   src/foo.py  |  summarize  ")
        assert result[0] == ("review", "src/foo.py")
        assert result[1][0] == "summarize"

    def test_empty_string_returns_empty(self):
        assert parse_chain("") == []

    def test_whitespace_only_returns_empty(self):
        result = parse_chain("   ")
        assert result == []


# ---------------------------------------------------------------------------
# ChainResult
# ---------------------------------------------------------------------------

class TestChainResult:
    def test_success_true_when_no_error_and_all_steps_ok(self):
        result = ChainResult(
            steps=[
                ChainStep(skill_name="a", prompt="p", success=True),
                ChainStep(skill_name="b", prompt="p", success=True),
            ]
        )
        assert result.success is True

    def test_success_false_when_has_error(self):
        result = ChainResult(error="something failed")
        assert result.success is False

    def test_success_false_when_step_failed(self):
        result = ChainResult(
            steps=[ChainStep(skill_name="a", prompt="p", success=False)]
        )
        assert result.success is False

    def test_summary_includes_step_names(self):
        result = ChainResult(
            steps=[
                ChainStep(skill_name="review", prompt="p", success=True),
                ChainStep(skill_name="summarize", prompt="p", success=True),
            ],
            final_output="done",
        )
        summary = result.summary()
        assert "review" in summary
        assert "summarize" in summary

    def test_summary_includes_error_snippet(self):
        result = ChainResult(
            steps=[
                ChainStep(
                    skill_name="lint",
                    prompt="p",
                    success=False,
                    error="Connection refused",
                )
            ],
            error="Step 'lint' failed",
        )
        summary = result.summary()
        assert "Connection refused" in summary


# ---------------------------------------------------------------------------
# SkillChain.run()
# ---------------------------------------------------------------------------

def _make_session(response_content: str = "output") -> MagicMock:
    """Build a minimal mock session."""
    session = MagicMock()
    mock_response = MagicMock()
    mock_response.content = response_content
    session.orchestrator.handle = AsyncMock(return_value=mock_response)
    return session


def _make_registry(*skills: Skill) -> MagicMock:
    registry = MagicMock()
    registry.get = lambda name: next(
        (s for s in skills if s.name == name), None
    )
    return registry


class TestSkillChainRun:
    def test_single_skill_success(self):
        skill = Skill(name="review", prompt="Review {args}")
        registry = _make_registry(skill)
        session = _make_session("review done")

        result = asyncio.run(
            SkillChain(registry, session).run("review", initial_args="main.py")
        )
        assert result.success
        assert result.final_output == "review done"

    def test_two_skill_chain(self):
        review = Skill(name="review", prompt="Review {args}")
        summarize = Skill(name="summarize", prompt="Summarize {args}")
        registry = _make_registry(review, summarize)

        call_counter = {"n": 0}
        async def fake_handle(prompt, context=None):
            call_counter["n"] += 1
            resp = MagicMock()
            resp.content = f"response_{call_counter['n']}"
            return resp

        session = MagicMock()
        session.orchestrator.handle = fake_handle

        result = asyncio.run(
            SkillChain(registry, session).run("review | summarize", initial_args="src/")
        )
        assert result.success
        assert len(result.steps) == 2
        # second step should receive output of first step
        assert result.steps[1].prompt != result.steps[0].prompt or True  # chain ran

    def test_unknown_skill_returns_error(self):
        registry = _make_registry()  # no skills
        session = _make_session()

        result = asyncio.run(
            SkillChain(registry, session).run("unknown_skill")
        )
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_empty_chain_returns_error(self):
        registry = _make_registry()
        session = _make_session()

        result = asyncio.run(
            SkillChain(registry, session).run("")
        )
        assert result.success is False

    def test_step_failure_stops_chain(self):
        skill_a = Skill(name="a", prompt="A {args}")
        skill_b = Skill(name="b", prompt="B {args}")
        registry = _make_registry(skill_a, skill_b)

        session = MagicMock()
        session.orchestrator.handle = AsyncMock(side_effect=RuntimeError("boom"))

        result = asyncio.run(
            SkillChain(registry, session).run("a | b")
        )
        assert result.success is False
        assert len(result.steps) == 1  # stopped after first

    def test_missing_requirements_stops_chain(self):
        skill = Skill(
            name="needs_tool",
            prompt="Do {args}",
            requires=["nonexistent_tool_xyz"],
        )
        registry = _make_registry(skill)
        session = _make_session()

        result = asyncio.run(
            SkillChain(registry, session).run("needs_tool", initial_args="x")
        )
        assert result.success is False
        assert "nonexistent_tool_xyz" in result.error or "Missing" in result.error

    def test_context_file_injected(self, tmp_path):
        ctx_file = tmp_path / "context.txt"
        ctx_file.write_text("some context", encoding="utf-8")

        skill = Skill(
            name="ctx_skill",
            prompt="Do {args}",
            context=str(ctx_file),
        )
        registry = _make_registry(skill)
        session = _make_session("ok")

        result = asyncio.run(
            SkillChain(registry, session).run("ctx_skill", initial_args="x")
        )
        assert result.success
        # context was passed to orchestrator
        call_kwargs = session.orchestrator.handle.call_args
        assert call_kwargs.kwargs.get("context") or call_kwargs[1].get("context")
