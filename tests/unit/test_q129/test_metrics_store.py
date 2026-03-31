"""Tests for lidco.telemetry.metrics_store."""
import time
import pytest
from lidco.telemetry.metrics_store import MetricPoint, MetricsStore


class TestMetricPoint:
    def test_fields(self):
        p = MetricPoint(name="cpu", value=0.5, timestamp=1.0)
        assert p.name == "cpu"
        assert p.value == 0.5
        assert p.tags == {}

    def test_with_tags(self):
        p = MetricPoint(name="mem", value=1024.0, timestamp=1.0, tags={"host": "srv1"})
        assert p.tags["host"] == "srv1"


class TestMetricsStore:
    def setup_method(self):
        self.store = MetricsStore()

    def test_record_returns_point(self):
        pt = self.store.record("cpu", 0.8)
        assert isinstance(pt, MetricPoint)
        assert pt.name == "cpu"
        assert pt.value == 0.8

    def test_record_sets_timestamp(self):
        before = time.time()
        pt = self.store.record("cpu", 0.5)
        after = time.time()
        assert before <= pt.timestamp <= after

    def test_record_with_tags(self):
        pt = self.store.record("mem", 512.0, tags={"host": "srv"})
        assert pt.tags["host"] == "srv"

    def test_get_series_empty(self):
        assert self.store.get_series("missing") == []

    def test_get_series_returns_all(self):
        self.store.record("x", 1)
        self.store.record("x", 2)
        series = self.store.get_series("x")
        assert len(series) == 2

    def test_last_returns_latest(self):
        self.store.record("x", 1)
        self.store.record("x", 2)
        assert self.store.last("x").value == 2

    def test_last_missing_returns_none(self):
        assert self.store.last("missing") is None

    def test_aggregate_avg(self):
        for v in [1, 2, 3]:
            self.store.record("n", v)
        assert self.store.aggregate("n", "avg") == 2.0

    def test_aggregate_sum(self):
        for v in [1, 2, 3]:
            self.store.record("n", v)
        assert self.store.aggregate("n", "sum") == 6.0

    def test_aggregate_min(self):
        for v in [3, 1, 2]:
            self.store.record("n", v)
        assert self.store.aggregate("n", "min") == 1.0

    def test_aggregate_max(self):
        for v in [3, 1, 2]:
            self.store.record("n", v)
        assert self.store.aggregate("n", "max") == 3.0

    def test_aggregate_count(self):
        for _ in range(5):
            self.store.record("n", 1)
        assert self.store.aggregate("n", "count") == 5.0

    def test_aggregate_last(self):
        for v in [10, 20, 30]:
            self.store.record("n", v)
        assert self.store.aggregate("n", "last") == 30.0

    def test_aggregate_empty_returns_zero(self):
        assert self.store.aggregate("missing") == 0.0

    def test_aggregate_unknown_fn_raises(self):
        self.store.record("n", 1)
        with pytest.raises(ValueError):
            self.store.aggregate("n", "bogus")

    def test_names(self):
        self.store.record("a", 1)
        self.store.record("b", 2)
        names = self.store.names()
        assert "a" in names
        assert "b" in names

    def test_clear_specific(self):
        self.store.record("a", 1)
        self.store.record("b", 2)
        self.store.clear("a")
        assert self.store.get_series("a") == []
        assert len(self.store.get_series("b")) == 1

    def test_clear_all(self):
        self.store.record("a", 1)
        self.store.record("b", 2)
        self.store.clear()
        assert len(self.store) == 0

    def test_len_total_points(self):
        self.store.record("a", 1)
        self.store.record("a", 2)
        self.store.record("b", 3)
        assert len(self.store) == 3

    def test_len_empty(self):
        assert len(self.store) == 0

    def test_get_series_returns_copy(self):
        self.store.record("x", 1)
        s1 = self.store.get_series("x")
        s1.clear()
        assert len(self.store.get_series("x")) == 1
