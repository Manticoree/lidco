"""Tests for BudgetTracker and AlertLevel — Q63 Task 429."""

from __future__ import annotations

import pytest


class TestAlertLevel:
    def test_warning_value(self):
        from lidco.ai.budget_alerts import AlertLevel
        assert AlertLevel.WARNING.value == "WARNING"

    def test_critical_value(self):
        from lidco.ai.budget_alerts import AlertLevel
        assert AlertLevel.CRITICAL.value == "CRITICAL"

    def test_exceeded_value(self):
        from lidco.ai.budget_alerts import AlertLevel
        assert AlertLevel.EXCEEDED.value == "EXCEEDED"


class TestBudgetAlert:
    def test_str_representation(self):
        from lidco.ai.budget_alerts import BudgetAlert, AlertLevel
        alert = BudgetAlert(level=AlertLevel.WARNING, period="daily", spent=4.1, limit=5.0, pct=82.0)
        s = str(alert)
        assert "WARNING" in s
        assert "daily" in s.lower()


class TestBudgetTracker:
    def test_initial_spend_zero(self):
        from lidco.ai.budget_alerts import BudgetTracker
        tracker = BudgetTracker(daily_limit_usd=5.0)
        assert tracker.daily_spend == 0.0
        assert tracker.monthly_spend == 0.0

    def test_record_cost_accumulates(self):
        from lidco.ai.budget_alerts import BudgetTracker
        tracker = BudgetTracker(daily_limit_usd=5.0)
        tracker.record_cost(1.0)
        tracker.record_cost(0.5)
        assert abs(tracker.daily_spend - 1.5) < 1e-9

    def test_check_limits_no_alerts_below_threshold(self):
        from lidco.ai.budget_alerts import BudgetTracker
        tracker = BudgetTracker(daily_limit_usd=10.0)
        tracker.record_cost(1.0)
        alerts = tracker.check_limits()
        assert len(alerts) == 0

    def test_check_limits_warning_at_80pct(self):
        from lidco.ai.budget_alerts import BudgetTracker, AlertLevel
        tracker = BudgetTracker(daily_limit_usd=10.0, monthly_limit_usd=100.0)
        tracker.record_cost(8.1)  # > 80%
        alerts = tracker.check_limits()
        levels = [a.level for a in alerts]
        assert AlertLevel.WARNING in levels or AlertLevel.CRITICAL in levels or AlertLevel.EXCEEDED in levels

    def test_check_limits_exceeded_at_100pct(self):
        from lidco.ai.budget_alerts import BudgetTracker, AlertLevel
        tracker = BudgetTracker(daily_limit_usd=5.0, monthly_limit_usd=0.0)
        tracker.record_cost(5.5)
        alerts = tracker.check_limits()
        levels = [a.level for a in alerts]
        assert AlertLevel.EXCEEDED in levels

    def test_alert_not_repeated(self):
        from lidco.ai.budget_alerts import BudgetTracker, AlertLevel
        tracker = BudgetTracker(daily_limit_usd=5.0, monthly_limit_usd=0.0)
        tracker.record_cost(4.5)  # 90% → CRITICAL
        alerts1 = tracker.check_limits()
        alerts2 = tracker.check_limits()  # should not fire again
        assert len(alerts2) == 0

    def test_reset_all_clears_spend(self):
        from lidco.ai.budget_alerts import BudgetTracker
        tracker = BudgetTracker(daily_limit_usd=5.0, monthly_limit_usd=50.0)
        tracker.record_cost(3.0)
        tracker.reset_all()
        assert tracker.daily_spend == 0.0
        assert tracker.monthly_spend == 0.0

    def test_status_dict(self):
        from lidco.ai.budget_alerts import BudgetTracker
        tracker = BudgetTracker(daily_limit_usd=5.0, monthly_limit_usd=50.0)
        tracker.record_cost(1.0)
        status = tracker.status()
        assert "daily_spend" in status
        assert "monthly_spend" in status

    def test_zero_limit_no_alerts(self):
        from lidco.ai.budget_alerts import BudgetTracker
        tracker = BudgetTracker(daily_limit_usd=0.0, monthly_limit_usd=0.0)
        tracker.record_cost(100.0)
        alerts = tracker.check_limits()
        assert alerts == []
