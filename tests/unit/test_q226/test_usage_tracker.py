"""Tests for lidco.gateway.usage_tracker."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from lidco.gateway.usage_tracker import UsageRecord, UsageTracker


class TestUsageRecord:
    def test_fields(self) -> None:
        rec = UsageRecord(key_id="k1", provider="openai", tokens=100, cost=0.01, timestamp=1.0)
        assert rec.tokens == 100
        assert rec.cost == 0.01


class TestUsageTracker:
    def test_record(self) -> None:
        tracker = UsageTracker()
        rec = tracker.record("k1", "openai", 100, 0.01)
        assert rec.key_id == "k1"
        assert rec.tokens == 100
        assert len(tracker.records()) == 1

    def test_total_all(self) -> None:
        tracker = UsageTracker()
        tracker.record("k1", "openai", 100, 0.01)
        tracker.record("k2", "anthropic", 200, 0.02)
        t = tracker.total()
        assert t["tokens"] == 300
        assert t["cost"] == pytest.approx(0.03)

    def test_total_filtered(self) -> None:
        tracker = UsageTracker()
        tracker.record("k1", "openai", 100, 0.01)
        tracker.record("k2", "anthropic", 200, 0.02)
        t = tracker.total(provider="openai")
        assert t["tokens"] == 100

    def test_daily_aggregation(self) -> None:
        tracker = UsageTracker()
        tracker.record("k1", "openai", 100, 0.01)
        tracker.record("k2", "openai", 200, 0.02)
        daily = tracker.daily()
        assert len(daily) == 1
        day = list(daily.values())[0]
        assert day["tokens"] == 300

    def test_daily_with_date_filter(self) -> None:
        tracker = UsageTracker()
        tracker.record("k1", "openai", 100, 0.01)
        today = time.strftime("%Y-%m-%d")
        daily = tracker.daily(date=today)
        assert today in daily

    def test_daily_with_wrong_date(self) -> None:
        tracker = UsageTracker()
        tracker.record("k1", "openai", 100, 0.01)
        daily = tracker.daily(date="1999-01-01")
        assert len(daily) == 0

    def test_monthly_aggregation(self) -> None:
        tracker = UsageTracker()
        tracker.record("k1", "openai", 100, 0.01)
        monthly = tracker.monthly()
        assert len(monthly) == 1
        month = list(monthly.values())[0]
        assert month["tokens"] == 100

    def test_quota_check_within_limit(self) -> None:
        tracker = UsageTracker(quota={"openai": 1000})
        tracker.record("k1", "openai", 300, 0.03)
        qc = tracker.quota_check("openai")
        assert qc["used"] == 300
        assert qc["limit"] == 1000
        assert qc["remaining"] == 700
        assert qc["percentage"] == 30.0

    def test_quota_check_no_quota(self) -> None:
        tracker = UsageTracker()
        qc = tracker.quota_check("openai")
        assert qc["limit"] == 0
        assert qc["remaining"] == 0

    def test_export_csv(self) -> None:
        tracker = UsageTracker()
        tracker.record("k1", "openai", 100, 0.01)
        csv_str = tracker.export_csv()
        assert "key_id" in csv_str
        assert "k1" in csv_str
        assert "openai" in csv_str

    def test_records_filtered(self) -> None:
        tracker = UsageTracker()
        tracker.record("k1", "openai", 100, 0.01)
        tracker.record("k2", "anthropic", 200, 0.02)
        recs = tracker.records(provider="anthropic")
        assert len(recs) == 1
        assert recs[0].provider == "anthropic"

    def test_summary(self) -> None:
        tracker = UsageTracker()
        tracker.record("k1", "openai", 100, 0.01)
        s = tracker.summary()
        assert s["total_records"] == 1
        assert s["total_tokens"] == 100
        assert "openai" in s["providers"]
