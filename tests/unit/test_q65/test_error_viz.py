"""Tests for ErrorViz — Q65 Task 443."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone


def make_error_history(records):
    """Create a mock ErrorHistory with given records."""
    history = MagicMock()
    history._records = records
    history.get_recent.return_value = records
    return history


def make_record(error_type, occurrence_count=1, ts=None):
    rec = MagicMock()
    rec.error_type = error_type
    rec.occurrence_count = occurrence_count
    rec.timestamp = ts or datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    return rec


class TestFrequencyByType:
    def test_empty_history(self):
        from lidco.analytics.error_viz import ErrorViz
        viz = ErrorViz()
        history = make_error_history([])
        result = viz.frequency_by_type(history)
        assert result == {}

    def test_counts_by_type(self):
        from lidco.analytics.error_viz import ErrorViz
        viz = ErrorViz()
        history = make_error_history([
            make_record("TypeError", 2),
            make_record("ValueError", 3),
            make_record("TypeError", 1),
        ])
        result = viz.frequency_by_type(history)
        assert result["TypeError"] == 3
        assert result["ValueError"] == 3


class TestFrequencyByTime:
    def test_empty_history(self):
        from lidco.analytics.error_viz import ErrorViz
        viz = ErrorViz()
        history = make_error_history([])
        result = viz.frequency_by_time(history)
        assert result == []

    def test_groups_by_hour(self):
        from lidco.analytics.error_viz import ErrorViz
        viz = ErrorViz()
        ts1 = datetime(2025, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
        ts2 = datetime(2025, 1, 1, 10, 30, 0, tzinfo=timezone.utc)
        ts3 = datetime(2025, 1, 1, 11, 5, 0, tzinfo=timezone.utc)
        history = make_error_history([
            make_record("E", 1, ts1),
            make_record("E", 1, ts2),
            make_record("E", 1, ts3),
        ])
        result = viz.frequency_by_time(history, bucket_minutes=60)
        assert len(result) >= 1


class TestAsciiBarChart:
    def test_empty_data(self):
        from lidco.analytics.error_viz import ErrorViz
        viz = ErrorViz()
        result = viz.ascii_bar_chart({}, title="Test")
        assert "no data" in result.lower() or "(no data)" in result

    def test_chart_contains_label(self):
        from lidco.analytics.error_viz import ErrorViz
        viz = ErrorViz()
        result = viz.ascii_bar_chart({"TypeError": 5, "ValueError": 3}, title="Errors")
        assert "TypeError" in result
        assert "ValueError" in result


class TestTimeSeriesChart:
    def test_empty_data(self):
        from lidco.analytics.error_viz import ErrorViz
        viz = ErrorViz()
        result = viz.time_series_chart([], title="Over Time")
        assert "no data" in result.lower() or "(no data)" in result

    def test_chart_contains_sparkline(self):
        from lidco.analytics.error_viz import ErrorViz, _SPARK_BLOCKS
        viz = ErrorViz()
        data = [("10:00", 5), ("11:00", 3), ("12:00", 7)]
        result = viz.time_series_chart(data, title="Errors")
        # Result should contain spark chars
        assert any(ch in result for ch in _SPARK_BLOCKS)


class TestRender:
    def test_render_returns_panel(self):
        from lidco.analytics.error_viz import ErrorViz
        from rich.panel import Panel
        viz = ErrorViz()
        history = make_error_history([
            make_record("TypeError", 2),
        ])
        result = viz.render(history)
        assert isinstance(result, Panel)

    def test_render_empty_history(self):
        from lidco.analytics.error_viz import ErrorViz
        from rich.panel import Panel
        viz = ErrorViz()
        history = make_error_history([])
        result = viz.render(history)
        assert isinstance(result, Panel)
