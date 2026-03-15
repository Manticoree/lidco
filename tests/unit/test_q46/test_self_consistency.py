"""Tests for SelfConsistencyChecker — Task 320."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.ai.self_consistency import (
    ConsistencyResult,
    SelfConsistencyChecker,
    _default_normalize,
)


def _mock_llm(*contents: str) -> MagicMock:
    llm = MagicMock()
    responses = []
    for c in contents:
        r = MagicMock()
        r.content = c
        responses.append(r)
    llm.complete = AsyncMock(side_effect=responses)
    return llm


# ---------------------------------------------------------------------------
# _default_normalize
# ---------------------------------------------------------------------------

class TestDefaultNormalize:
    def test_lowercase(self):
        assert _default_normalize("Hello World") == "hello world"

    def test_strips_trailing_punctuation(self):
        assert _default_normalize("The answer is 4.") == "the answer is 4"

    def test_collapses_whitespace(self):
        assert _default_normalize("a  b   c") == "a b c"


# ---------------------------------------------------------------------------
# ConsistencyResult
# ---------------------------------------------------------------------------

class TestConsistencyResult:
    def test_success_when_winner_set(self):
        r = ConsistencyResult(winner="42", consistency=0.8, n_samples=5)
        assert r.success is True

    def test_failure_when_error(self):
        r = ConsistencyResult(error="all failed")
        assert r.success is False

    def test_summary_shows_winner(self):
        r = ConsistencyResult(winner="4", consistency=0.8, n_samples=5)
        s = r.summary()
        assert "4" in s or "80" in s


# ---------------------------------------------------------------------------
# SelfConsistencyChecker.check()
# ---------------------------------------------------------------------------

class TestSelfConsistencyCheck:
    def test_majority_winner_selected(self):
        # 3 say "4", 1 says "five", 1 says "four"
        llm = _mock_llm("4", "4", "4", "five", "four")
        checker = SelfConsistencyChecker(llm, n=5)
        result = asyncio.run(checker.check([{"role": "user", "content": "2+2?"}]))
        assert result.winner == "4"
        assert result.consistency >= 0.5

    def test_single_sample(self):
        llm = _mock_llm("hello world")
        checker = SelfConsistencyChecker(llm, n=1)
        result = asyncio.run(checker.check([{"role": "user", "content": "say hello"}]))
        assert result.success
        assert result.winner == "hello world"

    def test_n_zero_returns_error(self):
        llm = MagicMock()
        checker = SelfConsistencyChecker(llm, n=0)
        result = asyncio.run(checker.check([{"role": "user", "content": "hi"}]))
        assert result.error

    def test_all_samples_fail(self):
        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=RuntimeError("error"))
        checker = SelfConsistencyChecker(llm, n=3)
        result = asyncio.run(checker.check([{"role": "user", "content": "hi"}]))
        assert result.success is False
        assert result.error

    def test_consistency_fraction_correct(self):
        # 4 out of 5 agree → consistency = 0.8
        llm = _mock_llm("yes", "yes", "yes", "yes", "no")
        checker = SelfConsistencyChecker(llm, n=5)
        result = asyncio.run(checker.check([{"role": "user", "content": "agree?"}]))
        assert abs(result.consistency - 0.8) < 0.01

    def test_vote_counts_populated(self):
        llm = _mock_llm("a", "b", "a")
        checker = SelfConsistencyChecker(llm, n=3)
        result = asyncio.run(checker.check([{"role": "user", "content": "x"}]))
        assert result.vote_counts.get("a", 0) == 2

    def test_custom_normalize(self):
        llm = _mock_llm("  RESULT  ", " result ", "RESULT")
        checker = SelfConsistencyChecker(
            llm, n=3, normalize_fn=lambda s: s.strip().lower()
        )
        result = asyncio.run(checker.check([{"role": "user", "content": "x"}]))
        assert result.consistency == 1.0

    def test_n_samples_recorded(self):
        llm = _mock_llm("a", "b", "c")
        checker = SelfConsistencyChecker(llm, n=3)
        result = asyncio.run(checker.check([{"role": "user", "content": "x"}]))
        assert result.n_samples == 3
