"""Tests for lidco.agents.result_aggregator."""
from __future__ import annotations

import pytest

from lidco.agents.result_aggregator import (
    AgentResult,
    AggregatedResult,
    ResultAggregator,
)


class TestAgentResult:
    def test_frozen(self) -> None:
        r = AgentResult(agent_name="a", content="hello")
        with pytest.raises(AttributeError):
            r.agent_name = "b"  # type: ignore[misc]

    def test_defaults(self) -> None:
        r = AgentResult(agent_name="a", content="x")
        assert r.confidence == 0.5
        assert r.metadata == ()


class TestResultAggregator:
    def test_add_result(self) -> None:
        agg = ResultAggregator()
        r = agg.add_result("agent1", "output", confidence=0.9)
        assert r.agent_name == "agent1"
        assert r.confidence == 0.9

    def test_merge_empty(self) -> None:
        agg = ResultAggregator()
        merged = agg.merge()
        assert merged.results == ()
        assert merged.merged_content == ""
        assert merged.consensus == 0.0

    def test_merge_single(self) -> None:
        agg = ResultAggregator()
        agg.add_result("a", "content a", confidence=0.8)
        merged = agg.merge()
        assert len(merged.results) == 1
        assert "content a" in merged.merged_content
        assert merged.consensus == 0.8

    def test_merge_multiple(self) -> None:
        agg = ResultAggregator()
        agg.add_result("a", "content a", confidence=0.6)
        agg.add_result("b", "content b", confidence=0.8)
        merged = agg.merge()
        assert len(merged.results) == 2
        assert "## a" in merged.merged_content
        assert "## b" in merged.merged_content
        assert merged.consensus == 0.7

    def test_rank_by_confidence(self) -> None:
        agg = ResultAggregator()
        agg.add_result("low", "x", confidence=0.1)
        agg.add_result("high", "y", confidence=0.9)
        agg.add_result("mid", "z", confidence=0.5)
        ranked = agg.rank_by_confidence()
        assert ranked[0].agent_name == "high"
        assert ranked[-1].agent_name == "low"

    def test_detect_conflicts_none(self) -> None:
        agg = ResultAggregator()
        agg.add_result("a", "hello world")
        agg.add_result("b", "hello there")
        conflicts = agg.detect_conflicts()
        assert conflicts == []

    def test_detect_conflicts_length_diff(self) -> None:
        agg = ResultAggregator()
        agg.add_result("a", "x")
        agg.add_result("b", "a very long result that is much bigger")
        conflicts = agg.detect_conflicts()
        assert len(conflicts) == 1
        assert ("a", "b") in conflicts

    def test_best_empty(self) -> None:
        agg = ResultAggregator()
        assert agg.best() is None

    def test_best(self) -> None:
        agg = ResultAggregator()
        agg.add_result("low", "x", confidence=0.2)
        agg.add_result("high", "y", confidence=0.95)
        best = agg.best()
        assert best is not None
        assert best.agent_name == "high"

    def test_summary(self) -> None:
        agg = ResultAggregator()
        assert "No results" in agg.summary()
        agg.add_result("a", "hello", confidence=0.7)
        s = agg.summary()
        assert "1 agents" in s
        assert "0.70" in s
