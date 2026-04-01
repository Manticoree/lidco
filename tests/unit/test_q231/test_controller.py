"""Tests for lidco.budget.controller."""
from __future__ import annotations

import pytest

from lidco.budget.controller import BudgetController, TurnResult


class TestTurnResult:
    def test_frozen(self) -> None:
        tr = TurnResult()
        with pytest.raises(AttributeError):
            tr.turn = 1  # type: ignore[misc]

    def test_defaults(self) -> None:
        tr = TurnResult()
        assert tr.turn == 0
        assert tr.tokens_used == 0
        assert tr.tokens_remaining == 0
        assert tr.compacted is False
        assert tr.alerts == ()
        assert tr.utilization == 0.0


class TestBudgetController:
    def test_init_defaults(self) -> None:
        ctrl = BudgetController()
        assert ctrl.utilization() == 0.0
        assert ctrl.remaining() == 128_000

    def test_process_turn_records_tokens(self) -> None:
        ctrl = BudgetController(context_limit=100_000)
        result = ctrl.process_turn("user", 10_000)
        assert result.turn == 1
        assert result.tokens_used == 10_000
        assert result.tokens_remaining == 90_000

    def test_process_turn_returns_turn_result(self) -> None:
        ctrl = BudgetController(context_limit=100_000)
        result = ctrl.process_turn("assistant", 5000)
        assert isinstance(result, TurnResult)
        assert result.utilization == 0.05

    def test_should_compact_below_threshold(self) -> None:
        ctrl = BudgetController(context_limit=100_000)
        ctrl.process_turn("user", 10_000)
        assert ctrl.should_compact() is False

    def test_should_compact_above_threshold(self) -> None:
        ctrl = BudgetController(context_limit=100_000, thresholds=(0.50, 0.70, 0.90))
        ctrl.process_turn("user", 55_000)
        assert ctrl.should_compact() is True

    def test_incur_and_outstanding_debt(self) -> None:
        ctrl = BudgetController()
        ctrl.incur_debt(5000, "overflow")
        assert ctrl.outstanding_debt() == 5000

    def test_get_forecast(self) -> None:
        ctrl = BudgetController()
        ctrl.process_turn("user", 1000)
        fc = ctrl.get_forecast()
        assert "current_used" in fc
        assert "recommendation" in fc

    def test_record_compaction(self) -> None:
        ctrl = BudgetController(context_limit=100_000)
        ctrl.process_turn("assistant", 80_000)
        ctrl.record_compaction(before=80_000, after=40_000)
        assert ctrl.remaining() > 20_000

    def test_reset_clears_state(self) -> None:
        ctrl = BudgetController(context_limit=100_000)
        ctrl.process_turn("user", 50_000)
        ctrl.incur_debt(1000)
        ctrl.reset()
        assert ctrl.utilization() == 0.0
        assert ctrl.outstanding_debt() == 0
        assert ctrl.remaining() == 100_000

    def test_summary_returns_string(self) -> None:
        ctrl = BudgetController()
        ctrl.process_turn("user", 5000)
        s = ctrl.summary()
        assert isinstance(s, str)
        assert "Context" in s

    def test_multiple_turns_accumulate(self) -> None:
        ctrl = BudgetController(context_limit=100_000)
        ctrl.process_turn("user", 10_000)
        ctrl.process_turn("assistant", 20_000)
        ctrl.process_turn("user", 5_000)
        assert ctrl.utilization() == pytest.approx(0.35, abs=0.01)
