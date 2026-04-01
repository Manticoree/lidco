"""Tests for CostAlertEngine."""

import time
from unittest.mock import patch

from lidco.economics.cost_alerts import AlertRule, CostAlert, CostAlertEngine


class TestCostAlertEngine:
    def test_add_and_list_rules(self):
        engine = CostAlertEngine()
        engine.add_rule(AlertRule(name="high-cost", alert_type="dollar", threshold=10.0))
        engine.add_rule(AlertRule(name="spike", alert_type="spike", threshold=3.0))
        assert len(engine.list_rules()) == 2

    def test_remove_rule(self):
        engine = CostAlertEngine()
        engine.add_rule(AlertRule(name="high-cost", alert_type="dollar", threshold=10.0))
        assert engine.remove_rule("high-cost") is True
        assert engine.remove_rule("nonexistent") is False
        assert len(engine.list_rules()) == 0

    def test_get_rule(self):
        engine = CostAlertEngine()
        engine.add_rule(AlertRule(name="high-cost", alert_type="dollar", threshold=10.0))
        rule = engine.get_rule("high-cost")
        assert rule is not None
        assert rule.alert_type == "dollar"
        assert engine.get_rule("nope") is None

    def test_dollar_threshold_alert(self):
        engine = CostAlertEngine()
        engine.add_rule(AlertRule(name="cap", alert_type="dollar", threshold=5.0, cooldown_seconds=0))
        # Below threshold
        alerts = engine.record_cost(3.0)
        assert len(alerts) == 0
        # Cross threshold
        alerts = engine.record_cost(3.0)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "dollar"
        assert alerts[0].rule_name == "cap"

    def test_percent_alert(self):
        engine = CostAlertEngine()
        engine.add_rule(AlertRule(name="pct", alert_type="percent", threshold=50.0, cooldown_seconds=0))
        # First entry: no alert (need 2+ entries)
        engine.record_cost(2.0)
        # Second entry: 3.0 is 150% of prev total 2.0 -> fires
        alerts = engine.record_cost(3.0)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "percent"

    def test_spike_alert(self):
        engine = CostAlertEngine()
        engine.add_rule(AlertRule(name="spike", alert_type="spike", threshold=3.0, cooldown_seconds=0))
        # Build baseline
        engine.record_cost(1.0)
        engine.record_cost(1.0)
        engine.record_cost(1.0)
        # Spike: 5.0 is 5x the average of 1.0
        alerts = engine.record_cost(5.0)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "spike"

    def test_cooldown_prevents_repeated_alerts(self):
        engine = CostAlertEngine()
        engine.add_rule(AlertRule(name="cap", alert_type="dollar", threshold=1.0, cooldown_seconds=9999))
        # First crosses threshold
        alerts1 = engine.record_cost(2.0)
        assert len(alerts1) == 1
        # Second should be blocked by cooldown
        alerts2 = engine.record_cost(1.0)
        assert len(alerts2) == 0

    def test_listener_callback(self):
        engine = CostAlertEngine()
        engine.add_rule(AlertRule(name="cap", alert_type="dollar", threshold=1.0, cooldown_seconds=0))
        captured = []
        engine.add_listener(lambda a: captured.append(a))
        engine.record_cost(2.0)
        assert len(captured) == 1
        assert captured[0].rule_name == "cap"

    def test_total_cost_and_history(self):
        engine = CostAlertEngine()
        engine.record_cost(1.5)
        engine.record_cost(2.5)
        assert engine.total_cost == 4.0
        assert engine.cost_history == [1.5, 2.5]

    def test_fired_alerts_property(self):
        engine = CostAlertEngine()
        engine.add_rule(AlertRule(name="cap", alert_type="dollar", threshold=1.0, cooldown_seconds=0))
        engine.record_cost(2.0)
        assert len(engine.fired_alerts) == 1

    def test_summary(self):
        engine = CostAlertEngine()
        engine.add_rule(AlertRule(name="cap", alert_type="dollar", threshold=5.0))
        engine.record_cost(1.0)
        s = engine.summary()
        assert "Total cost" in s
        assert "cap" in s
        assert "Rules: 1" in s
