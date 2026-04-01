"""Tests for lidco.budget.turn_manager."""
from __future__ import annotations

import unittest

from lidco.budget.turn_manager import TurnBudget, TurnBudgetManager


class TestTurnBudget(unittest.TestCase):
    def test_defaults(self) -> None:
        tb = TurnBudget()
        assert tb.turn == 0
        assert tb.pre_tokens == 0
        assert tb.delta == 0
        assert tb.compacted is False

    def test_frozen(self) -> None:
        tb = TurnBudget()
        with self.assertRaises(AttributeError):
            tb.turn = 5  # type: ignore[misc]


class TestTurnBudgetManager(unittest.TestCase):
    def test_begin_turn_increments(self) -> None:
        mgr = TurnBudgetManager()
        assert mgr.begin_turn(0) == 1
        assert mgr.begin_turn(100) == 2

    def test_end_turn_records(self) -> None:
        mgr = TurnBudgetManager()
        mgr.begin_turn(1000)
        tb = mgr.end_turn(1500)
        assert tb.turn == 1
        assert tb.pre_tokens == 1000
        assert tb.post_tokens == 1500
        assert tb.delta == 500

    def test_end_turn_compacted(self) -> None:
        mgr = TurnBudgetManager()
        mgr.begin_turn(5000)
        tb = mgr.end_turn(3000, compacted=True)
        assert tb.compacted is True
        assert tb.delta == -2000

    def test_get_turn(self) -> None:
        mgr = TurnBudgetManager()
        mgr.begin_turn(0)
        mgr.end_turn(100)
        mgr.begin_turn(100)
        mgr.end_turn(200)
        assert mgr.get_turn(1) is not None
        assert mgr.get_turn(1).post_tokens == 100
        assert mgr.get_turn(3) is None

    def test_get_recent(self) -> None:
        mgr = TurnBudgetManager()
        for i in range(10):
            mgr.begin_turn(i * 100)
            mgr.end_turn((i + 1) * 100)
        recent = mgr.get_recent(3)
        assert len(recent) == 3
        assert recent[-1].turn == 10

    def test_average_delta_empty(self) -> None:
        mgr = TurnBudgetManager()
        assert mgr.average_delta() == 0.0

    def test_average_delta(self) -> None:
        mgr = TurnBudgetManager()
        mgr.begin_turn(0)
        mgr.end_turn(100)
        mgr.begin_turn(100)
        mgr.end_turn(300)
        # deltas: 100, 200 => avg 150
        assert mgr.average_delta() == 150.0

    def test_should_warn_true(self) -> None:
        mgr = TurnBudgetManager(total_budget=1000)
        mgr.begin_turn(0)
        mgr.end_turn(800)
        # avg_delta=800, remaining=200, 800*5=4000 > 200
        assert mgr.should_warn() is True

    def test_should_warn_false(self) -> None:
        mgr = TurnBudgetManager(total_budget=100000)
        mgr.begin_turn(0)
        mgr.end_turn(100)
        # avg_delta=100, remaining=99900, 100*5=500 < 99900
        assert mgr.should_warn() is False

    def test_should_warn_empty(self) -> None:
        mgr = TurnBudgetManager()
        assert mgr.should_warn() is False

    def test_remaining(self) -> None:
        mgr = TurnBudgetManager(total_budget=10000)
        assert mgr.remaining(3000) == 7000
        assert mgr.remaining(20000) == 0

    def test_summary(self) -> None:
        mgr = TurnBudgetManager(total_budget=50000)
        mgr.begin_turn(0)
        mgr.end_turn(1000)
        text = mgr.summary()
        assert "50,000" in text
        assert "1" in text


if __name__ == "__main__":
    unittest.main()
