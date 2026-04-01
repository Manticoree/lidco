"""Tests for lidco.budget.importance_scorer."""
from __future__ import annotations

import pytest

from lidco.budget.importance_scorer import ImportanceScorer, ScoredMessage


class TestScoredMessage:
    def test_frozen(self) -> None:
        s = ScoredMessage(index=0, role="user")
        with pytest.raises(AttributeError):
            s.index = 1  # type: ignore[misc]

    def test_defaults(self) -> None:
        s = ScoredMessage(index=0, role="user")
        assert s.importance == 0.5
        assert s.reasons == ()
        assert s.pinned is False
        assert s.age_turns == 0


class TestImportanceScorer:
    def test_system_always_one(self) -> None:
        scorer = ImportanceScorer()
        msg = {"role": "system", "content": "prompt"}
        s = scorer.score(msg, index=0, current_turn=100)
        assert s.importance == 1.0

    def test_pinned_always_one(self) -> None:
        scorer = ImportanceScorer()
        msg = {"role": "user", "content": "hi"}
        s = scorer.score(msg, index=0, current_turn=100, pinned_indices={0})
        assert s.importance == 1.0
        assert s.pinned is True

    def test_code_block_high(self) -> None:
        scorer = ImportanceScorer()
        msg = {"role": "assistant", "content": "```python\nprint()```"}
        s = scorer.score(msg, index=0, current_turn=0)
        assert s.importance == 0.8

    def test_error_high(self) -> None:
        scorer = ImportanceScorer()
        msg = {"role": "assistant", "content": "Traceback: something failed"}
        s = scorer.score(msg, index=0, current_turn=0)
        assert s.importance == 0.9

    def test_user_question(self) -> None:
        scorer = ImportanceScorer()
        msg = {"role": "user", "content": "What is Python?"}
        s = scorer.score(msg, index=0, current_turn=0)
        assert s.importance == 0.7

    def test_short_assistant(self) -> None:
        scorer = ImportanceScorer()
        msg = {"role": "assistant", "content": "OK"}
        s = scorer.score(msg, index=0, current_turn=0)
        assert s.importance == 0.2

    def test_tool_result(self) -> None:
        scorer = ImportanceScorer()
        msg = {"role": "tool", "content": "file.py: success"}
        s = scorer.score(msg, index=0, current_turn=0)
        assert s.importance == 0.4

    def test_decay_over_age(self) -> None:
        scorer = ImportanceScorer(decay_per_turn=0.1)
        msg = {"role": "user", "content": "What is Python?"}
        s = scorer.score(msg, index=0, current_turn=5)
        # base 0.7 - 0.1*5 = 0.2
        assert abs(s.importance - 0.2) < 0.01

    def test_decay_floor_zero(self) -> None:
        scorer = ImportanceScorer(decay_per_turn=0.5)
        msg = {"role": "tool", "content": "result"}
        s = scorer.score(msg, index=0, current_turn=10)
        assert s.importance == 0.0

    def test_score_all(self) -> None:
        scorer = ImportanceScorer()
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "OK"},
        ]
        scored = scorer.score_all(msgs, current_turn=3)
        assert len(scored) == 3
        assert scored[0].importance == 1.0  # system

    def test_rank_ascending(self) -> None:
        scorer = ImportanceScorer()
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "assistant", "content": "OK"},
            {"role": "user", "content": "Question here?"},
        ]
        scored = scorer.score_all(msgs, current_turn=3)
        ranked = scorer.rank(scored)
        importances = [r.importance for r in ranked]
        assert importances == sorted(importances)

    def test_summary_output(self) -> None:
        scorer = ImportanceScorer()
        scored = [ScoredMessage(index=0, role="user", importance=0.7, reasons=("user question",))]
        s = scorer.summary(scored)
        assert "Scored 1" in s
        assert "0.70" in s
