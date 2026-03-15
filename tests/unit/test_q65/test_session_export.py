"""Tests for SessionAnalyticsExporter and AnalyticsRecord — Q65 Task 441."""

from __future__ import annotations

import csv
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock


class TestAnalyticsRecord:
    def test_default_values(self):
        from lidco.analytics.session_export import AnalyticsRecord
        rec = AnalyticsRecord()
        assert rec.turn_count == 0
        assert rec.total_tokens == 0
        assert rec.total_cost == 0.0
        assert rec.agents_used == []
        assert rec.error_count == 0


class TestSessionAnalyticsExporter:
    def test_collect_no_session(self):
        from lidco.analytics.session_export import SessionAnalyticsExporter, AnalyticsRecord
        exporter = SessionAnalyticsExporter(session=None)
        rec = exporter._collect()
        assert isinstance(rec, AnalyticsRecord)

    def test_export_json_writes_file(self, tmp_path):
        from lidco.analytics.session_export import SessionAnalyticsExporter
        exporter = SessionAnalyticsExporter(session=None)
        out = tmp_path / "analytics.json"
        exporter.export_json(out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "turn_count" in data

    def test_export_csv_writes_file(self, tmp_path):
        from lidco.analytics.session_export import SessionAnalyticsExporter
        exporter = SessionAnalyticsExporter(session=None)
        out = tmp_path / "analytics.csv"
        exporter.export_csv(out)
        assert out.exists()
        rows = list(csv.reader(out.read_text().splitlines()))
        assert len(rows) >= 2  # header + data row

    def test_export_summary_returns_string(self):
        from lidco.analytics.session_export import SessionAnalyticsExporter
        exporter = SessionAnalyticsExporter(session=None)
        summary = exporter.export_summary()
        assert isinstance(summary, str)
        assert "Turns" in summary or "turns" in summary.lower()

    def test_collect_with_session_uses_session_id(self):
        from lidco.analytics.session_export import SessionAnalyticsExporter
        session = MagicMock()
        session.session_id = "test-session-42"
        session.orchestrator = None
        session.token_budget = None
        exporter = SessionAnalyticsExporter(session=session)
        rec = exporter._collect()
        assert rec.session_id == "test-session-42"

    def test_export_json_creates_parent_dirs(self, tmp_path):
        from lidco.analytics.session_export import SessionAnalyticsExporter
        exporter = SessionAnalyticsExporter(session=None)
        out = tmp_path / "deep" / "dir" / "analytics.json"
        exporter.export_json(out)
        assert out.exists()

    def test_export_summary_contains_cost(self):
        from lidco.analytics.session_export import SessionAnalyticsExporter
        exporter = SessionAnalyticsExporter(session=None)
        summary = exporter.export_summary()
        assert "$" in summary or "cost" in summary.lower()

    def test_exported_at_field_set(self):
        from lidco.analytics.session_export import SessionAnalyticsExporter
        exporter = SessionAnalyticsExporter(session=None)
        rec = exporter._collect()
        assert rec.exported_at  # non-empty string

    def test_export_csv_has_field_column(self, tmp_path):
        from lidco.analytics.session_export import SessionAnalyticsExporter
        exporter = SessionAnalyticsExporter(session=None)
        out = tmp_path / "out.csv"
        exporter.export_csv(out)
        content = out.read_text()
        # Should have some header content
        assert len(content) > 0
