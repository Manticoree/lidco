"""Tests for AgentAnalytics — Task 438."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from lidco.analytics.agent_analytics import AgentAnalytics, AgentStats


class TestAgentStats:
    def test_default_values(self):
        s = AgentStats(agent_name="coder")
        assert s.total_calls == 0
        assert s.total_cost_usd == 0.0
        assert s.success_rate == 1.0
        assert s.error_count == 0


class TestRecordCall:
    def test_record_increments_calls(self, tmp_path):
        analytics = AgentAnalytics(project_dir=tmp_path)
        analytics.record_call("coder", 100, 50, 0.01, 200.0, True)
        stats = analytics.get_stats("coder")
        assert len(stats) == 1
        assert stats[0].total_calls == 1

    def test_record_accumulates_tokens(self, tmp_path):
        analytics = AgentAnalytics(project_dir=tmp_path)
        analytics.record_call("coder", 100, 50, 0.01, 200.0, True)
        analytics.record_call("coder", 200, 100, 0.02, 300.0, True)
        stats = analytics.get_stats("coder")[0]
        assert stats.total_tokens == 450

    def test_record_tracks_errors(self, tmp_path):
        analytics = AgentAnalytics(project_dir=tmp_path)
        analytics.record_call("coder", 100, 50, 0.01, 200.0, False)
        stats = analytics.get_stats("coder")[0]
        assert stats.error_count == 1
        assert stats.success_rate < 1.0

    def test_record_avg_duration(self, tmp_path):
        analytics = AgentAnalytics(project_dir=tmp_path)
        analytics.record_call("coder", 100, 50, 0.01, 100.0, True)
        analytics.record_call("coder", 100, 50, 0.01, 300.0, True)
        stats = analytics.get_stats("coder")[0]
        assert abs(stats.avg_duration_ms - 200.0) < 0.01


class TestGetStats:
    def test_get_all_stats(self, tmp_path):
        analytics = AgentAnalytics(project_dir=tmp_path)
        analytics.record_call("coder", 100, 50, 0.01, 100.0, True)
        analytics.record_call("tester", 200, 100, 0.02, 200.0, True)
        all_stats = analytics.get_stats()
        names = {s.agent_name for s in all_stats}
        assert "coder" in names
        assert "tester" in names

    def test_get_specific_agent(self, tmp_path):
        analytics = AgentAnalytics(project_dir=tmp_path)
        analytics.record_call("coder", 100, 50, 0.01, 100.0, True)
        stats = analytics.get_stats("coder")
        assert len(stats) == 1

    def test_get_missing_agent(self, tmp_path):
        analytics = AgentAnalytics(project_dir=tmp_path)
        assert analytics.get_stats("ghost") == []


class TestTopBy:
    def test_top_by_cost(self, tmp_path):
        analytics = AgentAnalytics(project_dir=tmp_path)
        analytics.record_call("cheap", 100, 50, 0.001, 100.0, True)
        analytics.record_call("expensive", 100, 50, 0.1, 100.0, True)
        top = analytics.top_by_cost(n=1)
        assert top[0].agent_name == "expensive"

    def test_top_by_calls(self, tmp_path):
        analytics = AgentAnalytics(project_dir=tmp_path)
        for _ in range(5):
            analytics.record_call("busy", 10, 5, 0.001, 50.0, True)
        analytics.record_call("lazy", 10, 5, 0.001, 50.0, True)
        top = analytics.top_by_calls(n=1)
        assert top[0].agent_name == "busy"


class TestPersistence:
    def test_saves_and_loads(self, tmp_path):
        a1 = AgentAnalytics(project_dir=tmp_path)
        a1.record_call("coder", 100, 50, 0.01, 100.0, True)

        a2 = AgentAnalytics(project_dir=tmp_path)
        stats = a2.get_stats("coder")
        assert len(stats) == 1
        assert stats[0].total_calls == 1


class TestRenderTable:
    def test_render_returns_table(self, tmp_path):
        from rich.table import Table
        analytics = AgentAnalytics(project_dir=tmp_path)
        analytics.record_call("coder", 100, 50, 0.01, 100.0, True)
        table = analytics.render_table()
        assert isinstance(table, Table)
