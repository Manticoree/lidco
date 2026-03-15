"""Tests for MultiModelSampler — Task 314."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.ai.sampler import MultiModelSampler, SamplerAttempt, SamplerResult, _default_critic


def _mock_llm(contents: list[str]) -> MagicMock:
    """LLM that returns successive responses."""
    llm = MagicMock()
    responses = []
    for c in contents:
        r = MagicMock()
        r.content = c
        responses.append(r)
    llm.complete = AsyncMock(side_effect=responses)
    return llm


def _const_llm(content: str = "result") -> MagicMock:
    llm = MagicMock()
    r = MagicMock()
    r.content = content
    llm.complete = AsyncMock(return_value=r)
    return llm


# ---------------------------------------------------------------------------
# SamplerAttempt
# ---------------------------------------------------------------------------

class TestSamplerAttempt:
    def test_success_when_response_present(self):
        r = MagicMock()
        r.content = "ok"
        a = SamplerAttempt(index=0, response=r)
        assert a.success is True

    def test_failure_when_error(self):
        a = SamplerAttempt(index=0, error="boom")
        assert a.success is False

    def test_content_property(self):
        r = MagicMock()
        r.content = "hello"
        a = SamplerAttempt(index=0, response=r)
        assert a.content == "hello"

    def test_content_no_response(self):
        a = SamplerAttempt(index=0)
        assert a.content == ""


# ---------------------------------------------------------------------------
# _default_critic
# ---------------------------------------------------------------------------

class TestDefaultCritic:
    def _make_attempt(self, index: int, content: str) -> SamplerAttempt:
        r = MagicMock()
        r.content = content
        return SamplerAttempt(index=index, response=r)

    def test_picks_longest(self):
        attempts = [
            self._make_attempt(0, "short"),
            self._make_attempt(1, "much longer response here"),
            self._make_attempt(2, "medium length"),
        ]
        best = _default_critic(attempts)
        assert best.index == 1

    def test_skips_failed_attempts(self):
        r = MagicMock()
        r.content = "good"
        failed = SamplerAttempt(index=0, error="failed")
        good = SamplerAttempt(index=1, response=r)
        best = _default_critic([failed, good])
        assert best.index == 1


# ---------------------------------------------------------------------------
# MultiModelSampler.sample()
# ---------------------------------------------------------------------------

class TestMultiModelSampler:
    def test_returns_n_attempts(self):
        llm = _const_llm("response")
        sampler = MultiModelSampler(llm)
        result = asyncio.run(sampler.sample([{"role": "user", "content": "hi"}], n=3))
        assert len(result.attempts) == 3

    def test_best_is_selected(self):
        llm = _mock_llm(["short", "much longer answer here", "medium"])
        sampler = MultiModelSampler(llm)
        result = asyncio.run(sampler.sample([{"role": "user", "content": "hi"}], n=3))
        assert result.best is not None
        assert result.best.content == "much longer answer here"

    def test_custom_critic(self):
        llm = _mock_llm(["aaa", "b", "cc"])
        sampler = MultiModelSampler(llm)
        # Custom critic: pick shortest
        def shortest(attempts):
            return min(
                [a for a in attempts if a.success],
                key=lambda a: len(a.content),
            )
        result = asyncio.run(
            sampler.sample([{"role": "user", "content": "hi"}], n=3, critic=shortest)
        )
        assert result.best.content == "b"

    def test_n_zero_returns_error(self):
        llm = _const_llm()
        sampler = MultiModelSampler(llm)
        result = asyncio.run(sampler.sample([{"role": "user", "content": "hi"}], n=0))
        assert result.error

    def test_failed_attempts_reported(self):
        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=RuntimeError("error"))
        sampler = MultiModelSampler(llm)
        result = asyncio.run(sampler.sample([{"role": "user", "content": "hi"}], n=2))
        assert result.n_successful == 0

    def test_model_cycling(self):
        llm = _const_llm("ok")
        sampler = MultiModelSampler(llm, models=["model-a", "model-b"])
        assert sampler._pick_model(0, None) == "model-a"
        assert sampler._pick_model(1, None) == "model-b"
        assert sampler._pick_model(2, None) == "model-a"

    def test_override_model_used(self):
        llm = _const_llm("ok")
        sampler = MultiModelSampler(llm, models=["model-a"])
        assert sampler._pick_model(0, "override-model") == "override-model"

    def test_success_count(self):
        llm = _mock_llm(["r1", "r2", "r3"])
        sampler = MultiModelSampler(llm)
        result = asyncio.run(sampler.sample([{"role": "user", "content": "hi"}], n=3))
        assert result.n_successful == 3
