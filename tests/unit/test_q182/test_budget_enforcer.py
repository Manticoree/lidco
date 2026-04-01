"""Tests for BudgetEnforcer."""

import json
import pytest

from lidco.economics.budget_enforcer import (
    BudgetEnforcer,
    BudgetExceededError,
    BudgetEvent,
    BudgetLimit,
    BudgetUsage,
)


class TestBudgetLimit:
    def test_defaults(self):
        bl = BudgetLimit(name="daily", limit_dollars=10.0)
        assert bl.warn_threshold == 0.8
        assert bl.hard_stop is True


class TestBudgetEnforcer:
    def test_add_and_list_budgets(self):
        enforcer = BudgetEnforcer()
        enforcer.add_budget(BudgetLimit(name="daily", limit_dollars=5.0))
        enforcer.add_budget(BudgetLimit(name="monthly", limit_dollars=100.0))
        assert len(enforcer.list_budgets()) == 2

    def test_remove_budget(self):
        enforcer = BudgetEnforcer()
        enforcer.add_budget(BudgetLimit(name="daily", limit_dollars=5.0))
        assert enforcer.remove_budget("daily") is True
        assert enforcer.remove_budget("nonexistent") is False
        assert len(enforcer.list_budgets()) == 0

    def test_get_budget(self):
        enforcer = BudgetEnforcer()
        enforcer.add_budget(BudgetLimit(name="daily", limit_dollars=5.0))
        usage = enforcer.get_budget("daily")
        assert usage is not None
        assert usage.budget.name == "daily"
        assert enforcer.get_budget("nope") is None

    def test_record_spend_returns_events(self):
        enforcer = BudgetEnforcer()
        enforcer.add_budget(BudgetLimit(name="daily", limit_dollars=10.0))
        events = enforcer.record_spend(3.0)
        assert len(events) >= 1
        assert events[0].event_type == "record"
        assert events[0].spent == 3.0

    def test_warning_threshold(self):
        enforcer = BudgetEnforcer()
        enforcer.add_budget(BudgetLimit(name="daily", limit_dollars=10.0, warn_threshold=0.8))
        # Spend 8.5 to cross the 80% warning threshold
        events = enforcer.record_spend(8.5)
        event_types = [e.event_type for e in events]
        assert "warning" in event_types

    def test_exceeded_raises_error(self):
        enforcer = BudgetEnforcer()
        enforcer.add_budget(BudgetLimit(name="daily", limit_dollars=5.0, hard_stop=True))
        with pytest.raises(BudgetExceededError) as exc_info:
            enforcer.record_spend(6.0)
        assert exc_info.value.budget_name == "daily"
        assert exc_info.value.spent == 6.0
        assert exc_info.value.limit == 5.0

    def test_check_allowed(self):
        enforcer = BudgetEnforcer()
        enforcer.add_budget(BudgetLimit(name="daily", limit_dollars=10.0, hard_stop=True))
        enforcer.record_spend(7.0)
        assert enforcer.check_allowed(2.0) is True
        assert enforcer.check_allowed(4.0) is False

    def test_reset_budget(self):
        enforcer = BudgetEnforcer()
        enforcer.add_budget(BudgetLimit(name="daily", limit_dollars=10.0))
        enforcer.record_spend(5.0)
        assert enforcer.reset_budget("daily") is True
        usage = enforcer.get_budget("daily")
        assert usage.spent_dollars == 0.0
        assert enforcer.reset_budget("nope") is False

    def test_persistence(self, tmp_path):
        path = tmp_path / "budgets.json"
        enforcer = BudgetEnforcer(persist_path=path)
        enforcer.add_budget(BudgetLimit(name="daily", limit_dollars=10.0))
        enforcer.record_spend(3.0)

        # Reload from disk
        enforcer2 = BudgetEnforcer(persist_path=path)
        usage = enforcer2.get_budget("daily")
        assert usage is not None
        assert usage.spent_dollars == 3.0

    def test_listener_called(self):
        enforcer = BudgetEnforcer()
        enforcer.add_budget(BudgetLimit(name="daily", limit_dollars=10.0))
        captured = []
        enforcer.add_listener(lambda evt: captured.append(evt))
        enforcer.record_spend(1.0)
        assert len(captured) >= 1
        assert captured[0].event_type == "record"

    def test_summary(self):
        enforcer = BudgetEnforcer()
        assert "No budgets" in enforcer.summary()
        enforcer.add_budget(BudgetLimit(name="daily", limit_dollars=10.0))
        enforcer.record_spend(2.0)
        s = enforcer.summary()
        assert "daily" in s
        assert "Budget Status" in s
