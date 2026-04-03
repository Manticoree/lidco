"""Tests for Q243 ContextScheduler."""
from __future__ import annotations

import pytest

from lidco.context.scheduler import ContextEntry, ContextScheduler


def _entry(eid: str, priority: int = 5, tokens: int = 100, category: str = "general") -> ContextEntry:
    return ContextEntry(id=eid, content="x" * (tokens * 4), priority=priority, category=category, token_estimate=tokens)


class TestContextSchedulerAdd:
    def test_add_single(self):
        s = ContextScheduler()
        s.add(_entry("a"))
        assert len(s.entries) == 1

    def test_add_multiple(self):
        s = ContextScheduler()
        s.add(_entry("a"))
        s.add(_entry("b"))
        assert len(s.entries) == 2

    def test_add_replaces_same_id(self):
        s = ContextScheduler()
        s.add(_entry("a", priority=1))
        s.add(_entry("a", priority=9))
        assert len(s.entries) == 1
        assert s.get("a").priority == 9


class TestContextSchedulerRemove:
    def test_remove_existing(self):
        s = ContextScheduler()
        s.add(_entry("a"))
        assert s.remove("a") is True
        assert len(s.entries) == 0

    def test_remove_missing(self):
        s = ContextScheduler()
        assert s.remove("nope") is False

    def test_remove_does_not_affect_others(self):
        s = ContextScheduler()
        s.add(_entry("a"))
        s.add(_entry("b"))
        s.remove("a")
        assert s.get("b") is not None


class TestContextSchedulerSchedule:
    def test_schedule_fits_all(self):
        s = ContextScheduler()
        s.add(_entry("a", tokens=50))
        s.add(_entry("b", tokens=50))
        result = s.schedule(200)
        assert len(result) == 2

    def test_schedule_budget_too_small(self):
        s = ContextScheduler()
        s.add(_entry("a", tokens=100))
        result = s.schedule(50)
        assert len(result) == 0

    def test_schedule_picks_highest_priority(self):
        s = ContextScheduler()
        s.add(_entry("low", priority=1, tokens=100))
        s.add(_entry("high", priority=10, tokens=100))
        result = s.schedule(100)
        assert len(result) == 1
        assert result[0].id == "high"

    def test_schedule_respects_budget(self):
        s = ContextScheduler()
        s.add(_entry("a", priority=10, tokens=60))
        s.add(_entry("b", priority=5, tokens=60))
        result = s.schedule(100)
        assert len(result) == 1
        assert result[0].id == "a"

    def test_schedule_empty(self):
        s = ContextScheduler()
        assert s.schedule(1000) == []

    def test_schedule_increments_count(self):
        s = ContextScheduler()
        s.schedule(100)
        s.schedule(100)
        assert s.stats()["schedule_count"] == 2


class TestContextSchedulerPreempt:
    def test_preempt_removes_lower_priority(self):
        s = ContextScheduler()
        s.add(_entry("high", priority=10))
        s.add(_entry("low", priority=1))
        assert s.preempt("high") is True
        assert s.get("low") is None

    def test_preempt_no_victim_if_all_higher(self):
        s = ContextScheduler()
        s.add(_entry("low", priority=1))
        s.add(_entry("high", priority=10))
        assert s.preempt("low") is False

    def test_preempt_missing_entry(self):
        s = ContextScheduler()
        assert s.preempt("nope") is False

    def test_preempt_single_entry(self):
        s = ContextScheduler()
        s.add(_entry("only", priority=5))
        assert s.preempt("only") is False


class TestContextSchedulerStats:
    def test_stats_empty(self):
        s = ContextScheduler()
        st = s.stats()
        assert st["entry_count"] == 0
        assert st["total_tokens"] == 0

    def test_stats_with_entries(self):
        s = ContextScheduler()
        s.add(_entry("a", tokens=100, category="code"))
        s.add(_entry("b", tokens=200, category="docs"))
        st = s.stats()
        assert st["entry_count"] == 2
        assert st["total_tokens"] == 300
        assert st["categories"] == {"code": 1, "docs": 1}

    def test_stats_preempt_count(self):
        s = ContextScheduler()
        s.add(_entry("high", priority=10))
        s.add(_entry("low", priority=1))
        s.preempt("high")
        assert s.stats()["preempt_count"] == 1
