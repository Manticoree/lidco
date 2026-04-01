"""Tests for lidco.agents.budget_splitter."""
from __future__ import annotations

import pytest

from lidco.agents.budget_splitter import (
    BudgetAllocation,
    BudgetSplitter,
    SplitMode,
)


class TestBudgetAllocation:
    def test_frozen(self) -> None:
        a = BudgetAllocation(agent_name="x")
        with pytest.raises(AttributeError):
            a.agent_name = "y"  # type: ignore[misc]

    def test_defaults(self) -> None:
        a = BudgetAllocation(agent_name="x")
        assert a.tokens == 0
        assert a.cost_limit == 0.0
        assert a.priority == 1


class TestBudgetSplitter:
    def test_equal_split(self) -> None:
        s = BudgetSplitter(total_tokens=1000, total_cost=10.0)
        allocs = s.split(["a", "b"], mode=SplitMode.EQUAL)
        assert len(allocs) == 2
        assert allocs[0].tokens == 500
        assert allocs[1].tokens == 500
        assert allocs[0].cost_limit == pytest.approx(5.0)

    def test_proportional_split(self) -> None:
        s = BudgetSplitter(total_tokens=1000, total_cost=10.0)
        allocs = s.split(
            ["a", "b"],
            mode=SplitMode.PROPORTIONAL,
            priorities={"a": 3, "b": 1},
        )
        assert allocs[0].tokens == 750
        assert allocs[1].tokens == 250

    def test_priority_split(self) -> None:
        s = BudgetSplitter(total_tokens=1000, total_cost=10.0)
        allocs = s.split(
            ["a", "b", "c"],
            mode=SplitMode.PRIORITY,
            priorities={"a": 3, "b": 1, "c": 1},
        )
        # a gets 50% = 500, b and c split remaining 500
        top = [a for a in allocs if a.agent_name == "a"]
        rest = [a for a in allocs if a.agent_name != "a"]
        assert top[0].tokens == 500
        assert all(r.tokens == 250 for r in rest)

    def test_empty_agents(self) -> None:
        s = BudgetSplitter(total_tokens=1000)
        allocs = s.split([])
        assert allocs == []

    def test_rebalance(self) -> None:
        s = BudgetSplitter(total_tokens=1000)
        allocs = [
            BudgetAllocation(agent_name="a", tokens=500),
            BudgetAllocation(agent_name="b", tokens=500),
        ]
        rebalanced = s.rebalance(allocs, completed=["a"])
        assert len(rebalanced) == 1
        assert rebalanced[0].agent_name == "b"
        assert rebalanced[0].tokens == 1000

    def test_rebalance_all_completed(self) -> None:
        s = BudgetSplitter(total_tokens=1000)
        allocs = [BudgetAllocation(agent_name="a", tokens=500)]
        rebalanced = s.rebalance(allocs, completed=["a"])
        assert rebalanced == []

    def test_check_budget_within(self) -> None:
        s = BudgetSplitter(total_tokens=1000)
        allocs = [BudgetAllocation(agent_name="a", tokens=500)]
        assert s.check_budget("a", 400, allocs) is True

    def test_check_budget_exceeded(self) -> None:
        s = BudgetSplitter(total_tokens=1000)
        allocs = [BudgetAllocation(agent_name="a", tokens=500)]
        assert s.check_budget("a", 600, allocs) is False

    def test_check_budget_unknown_agent(self) -> None:
        s = BudgetSplitter(total_tokens=1000)
        assert s.check_budget("unknown", 100, []) is False

    def test_summary(self) -> None:
        s = BudgetSplitter(total_tokens=1000, total_cost=5.0)
        allocs = s.split(["a"], mode=SplitMode.EQUAL)
        summary = s.summary(allocs)
        assert "1000 tokens" in summary
        assert "$5.00" in summary
