"""Tests for memory staleness decay — T499."""
from __future__ import annotations
import time
import pytest
from lidco.memory.staleness import StalenessRanker, freshness_score, staleness_score


class FakeMemory:
    def __init__(self, content: str, created_at: float | None = None, use_count: int = 0):
        self.content = content
        self.created_at = created_at or time.time()
        self.use_count = use_count


class TestStalenessScore:
    def test_new_memory_low_staleness(self):
        m = FakeMemory("fresh", created_at=time.time(), use_count=0)
        score = staleness_score(m)
        assert score < 1.0

    def test_old_memory_high_staleness(self):
        old_time = time.time() - 30 * 86400  # 30 days ago
        m = FakeMemory("old", created_at=old_time, use_count=0)
        score = staleness_score(m)
        assert score > 10.0

    def test_high_use_count_reduces_staleness(self):
        old_time = time.time() - 30 * 86400
        rarely_used = FakeMemory("x", created_at=old_time, use_count=0)
        often_used = FakeMemory("x", created_at=old_time, use_count=100)
        assert staleness_score(rarely_used) > staleness_score(often_used)

    def test_freshness_inverse_of_staleness(self):
        m = FakeMemory("x", created_at=time.time())
        s = staleness_score(m)
        f = freshness_score(m)
        assert abs(f - 1.0 / (1.0 + s)) < 1e-9


class TestStalenessRanker:
    def test_rank_fresh_first(self):
        old = FakeMemory("old", created_at=time.time() - 30 * 86400)
        fresh = FakeMemory("fresh", created_at=time.time())
        ranker = StalenessRanker()
        ranked = ranker.rank([old, fresh])
        assert ranked[0].content == "fresh"

    def test_expire_removes_old(self):
        old = FakeMemory("old", created_at=time.time() - 10 * 86400)
        fresh = FakeMemory("fresh", created_at=time.time())
        ranker = StalenessRanker()
        result = ranker.expire([old, fresh], ttl_days=7)
        assert all(m.content != "old" for m in result)
        assert any(m.content == "fresh" for m in result)

    def test_expire_keeps_within_ttl(self):
        recent = FakeMemory("recent", created_at=time.time() - 2 * 86400)
        ranker = StalenessRanker()
        result = ranker.expire([recent], ttl_days=7)
        assert len(result) == 1

    def test_split_fresh_stale(self):
        old = FakeMemory("old", created_at=time.time() - 30 * 86400)
        fresh = FakeMemory("fresh", created_at=time.time())
        ranker = StalenessRanker()
        f, s = ranker.split_fresh_stale([old, fresh], threshold=7.0)
        assert any(m.content == "fresh" for m in f)
        assert any(m.content == "old" for m in s)
