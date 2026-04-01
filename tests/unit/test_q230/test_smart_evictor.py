"""Tests for lidco.budget.smart_evictor."""
from __future__ import annotations

import pytest

from lidco.budget.smart_evictor import EvictionResult, SmartEvictor


class TestEvictionResult:
    def test_frozen(self) -> None:
        r = EvictionResult(evicted_count=0)
        with pytest.raises(AttributeError):
            r.evicted_count = 1  # type: ignore[misc]

    def test_defaults(self) -> None:
        r = EvictionResult(evicted_count=0)
        assert r.tokens_freed == 0
        assert r.evicted_indices == ()
        assert r.remaining_count == 0


class TestSmartEvictor:
    def _make_messages(self) -> list[dict]:
        return [
            {"role": "system", "content": "System prompt here."},
            {"role": "user", "content": "Hello there!" * 10},
            {"role": "assistant", "content": "OK"},
            {"role": "tool", "content": "result data" * 5},
            {"role": "user", "content": "Bye"},
            {"role": "assistant", "content": "Goodbye!"},
        ]

    def _make_scored(self, messages: list[dict]) -> list[dict]:
        scores = [1.0, 0.7, 0.2, 0.4, 0.7, 0.5]
        return [
            {"index": i, "importance": scores[i]}
            for i in range(len(messages))
        ]

    def test_evict_frees_tokens(self) -> None:
        e = SmartEvictor(min_keep=2)
        msgs = self._make_messages()
        scored = self._make_scored(msgs)
        remaining, result = e.evict(msgs, scored, target_tokens=1)
        assert result.evicted_count >= 1
        assert result.tokens_freed > 0
        assert len(remaining) == result.remaining_count

    def test_evict_never_removes_system(self) -> None:
        e = SmartEvictor(min_keep=0)
        msgs = self._make_messages()
        scored = self._make_scored(msgs)
        remaining, result = e.evict(msgs, scored, target_tokens=100000)
        roles = [m["role"] for m in remaining]
        assert "system" in roles

    def test_evict_respects_min_keep(self) -> None:
        e = SmartEvictor(min_keep=3)
        msgs = self._make_messages()
        scored = self._make_scored(msgs)
        remaining, result = e.evict(msgs, scored, target_tokens=100000)
        # System (1) + min_keep (3) = at least 4
        assert len(remaining) >= 4

    def test_evict_by_count(self) -> None:
        e = SmartEvictor(min_keep=2)
        msgs = self._make_messages()
        scored = self._make_scored(msgs)
        remaining, result = e.evict_by_count(msgs, scored, count=2)
        assert result.evicted_count == 2
        assert len(remaining) == 4

    def test_evict_by_count_respects_protection(self) -> None:
        e = SmartEvictor(min_keep=4)
        msgs = self._make_messages()
        scored = self._make_scored(msgs)
        # Only index 1 is evictable (system=0 protected, last 4 protected)
        remaining, result = e.evict_by_count(msgs, scored, count=10)
        assert result.evicted_count <= 1

    def test_can_evict(self) -> None:
        e = SmartEvictor(min_keep=2)
        msgs = self._make_messages()
        count = e.can_evict(msgs)
        # 6 total - 1 system - 2 min_keep = 3
        assert count == 3

    def test_can_evict_empty(self) -> None:
        e = SmartEvictor(min_keep=4)
        assert e.can_evict([]) == 0

    def test_can_evict_all_system(self) -> None:
        e = SmartEvictor(min_keep=0)
        msgs = [{"role": "system", "content": "a"}, {"role": "system", "content": "b"}]
        assert e.can_evict(msgs) == 0

    def test_summary(self) -> None:
        e = SmartEvictor()
        r = EvictionResult(evicted_count=3, tokens_freed=100, remaining_count=5)
        s = e.summary(r)
        assert "3" in s
        assert "100" in s

    def test_evict_zero_target(self) -> None:
        e = SmartEvictor(min_keep=2)
        msgs = self._make_messages()
        scored = self._make_scored(msgs)
        remaining, result = e.evict(msgs, scored, target_tokens=0)
        assert result.evicted_count == 0
        assert len(remaining) == len(msgs)
