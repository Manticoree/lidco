"""Tests for CostDashboard — Task 437."""

from __future__ import annotations

import time
import pytest
from lidco.analytics.dashboard import CostDashboard, CostSample


def make_sample(agent: str = "coder", cost: float = 0.001) -> CostSample:
    return CostSample(
        timestamp=time.time(),
        agent=agent,
        tokens_in=100,
        tokens_out=50,
        cost_usd=cost,
    )


class TestCostSample:
    def test_fields(self):
        s = make_sample()
        assert s.agent == "coder"
        assert s.tokens_in == 100
        assert s.tokens_out == 50
        assert s.cost_usd == 0.001


class TestCostDashboardRecord:
    def test_record_single(self):
        dash = CostDashboard()
        dash.record(make_sample(cost=0.01))
        assert len(dash._samples) == 1

    def test_record_keeps_last_1000(self):
        dash = CostDashboard()
        for _ in range(1005):
            dash.record(make_sample())
        assert len(dash._samples) == 1000

    def test_total_cost(self):
        dash = CostDashboard()
        dash.record(make_sample(cost=0.01))
        dash.record(make_sample(cost=0.02))
        assert abs(dash.total_cost() - 0.03) < 1e-9

    def test_total_tokens_in(self):
        dash = CostDashboard()
        dash.record(make_sample())
        dash.record(make_sample())
        assert dash.total_tokens_in() == 200

    def test_total_tokens_out(self):
        dash = CostDashboard()
        dash.record(make_sample())
        assert dash.total_tokens_out() == 50


class TestPerAgentCost:
    def test_per_agent(self):
        dash = CostDashboard()
        dash.record(make_sample("coder", 0.01))
        dash.record(make_sample("coder", 0.02))
        dash.record(make_sample("tester", 0.05))
        costs = dash.per_agent_cost()
        assert abs(costs["coder"] - 0.03) < 1e-9
        assert abs(costs["tester"] - 0.05) < 1e-9

    def test_last_n_turn_costs(self):
        dash = CostDashboard()
        for i in range(15):
            dash.record(make_sample(cost=float(i) * 0.001))
        last = dash.last_n_turn_costs(10)
        assert len(last) == 10
        # last 10 should be indices 5..14
        assert abs(last[0] - 0.005) < 1e-9


class TestSparkline:
    def test_empty(self):
        assert CostDashboard.sparkline([]) == ""

    def test_single(self):
        result = CostDashboard.sparkline([1.0])
        assert len(result) == 1

    def test_uniform_values(self):
        result = CostDashboard.sparkline([1.0, 1.0, 1.0])
        # All same value → all same block
        assert len(set(result)) == 1

    def test_width_limiting(self):
        values = list(range(100))
        result = CostDashboard.sparkline(values, width=20)
        assert len(result) == 20

    def test_contains_valid_chars(self):
        from lidco.analytics.dashboard import _SPARK_BLOCKS
        result = CostDashboard.sparkline([1.0, 2.0, 3.0, 4.0])
        for ch in result:
            assert ch in _SPARK_BLOCKS


class TestRender:
    def test_render_returns_layout(self):
        from rich.layout import Layout
        dash = CostDashboard()
        dash.record(make_sample("coder", 0.01))
        layout = dash.render()
        assert isinstance(layout, Layout)

    def test_render_empty(self):
        from rich.layout import Layout
        dash = CostDashboard()
        layout = dash.render()
        assert isinstance(layout, Layout)
