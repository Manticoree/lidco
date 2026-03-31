"""Tests for lidco.telemetry.timer."""
import time
import pytest
from lidco.telemetry.metrics_store import MetricsStore
from lidco.telemetry.timer import Timer, TimerRegistry, TimingRecord


class TestTimingRecord:
    def test_fields(self):
        r = TimingRecord(name="t", elapsed=0.1, started_at=1.0, ended_at=1.1)
        assert r.name == "t"
        assert r.elapsed == pytest.approx(0.1)


class TestTimer:
    def test_name(self):
        t = Timer("op")
        assert t.name == "op"

    def test_start_stop(self):
        t = Timer("op")
        t.start()
        time.sleep(0.01)
        record = t.stop()
        assert isinstance(record, TimingRecord)
        assert record.elapsed >= 0.01

    def test_stop_without_start_raises(self):
        t = Timer("op")
        with pytest.raises(RuntimeError):
            t.stop()

    def test_records_to_store(self):
        store = MetricsStore()
        t = Timer("op", store=store)
        t.start()
        t.stop()
        assert len(store.get_series("op")) == 1

    def test_no_store_no_error(self):
        t = Timer("op")
        t.start()
        record = t.stop()
        assert record.elapsed >= 0

    def test_measure_context_manager(self):
        t = Timer("op")
        with t.measure():
            time.sleep(0.01)
        # After context, timer is stopped

    def test_measure_records_to_store(self):
        store = MetricsStore()
        t = Timer("op", store=store)
        with t.measure():
            pass
        assert len(store.get_series("op")) == 1

    def test_record_timestamps(self):
        t = Timer("op")
        before = time.time()
        t.start()
        time.sleep(0.01)
        record = t.stop()
        after = time.time()
        assert before <= record.started_at <= after
        assert record.started_at <= record.ended_at

    def test_elapsed_is_difference(self):
        t = Timer("op")
        t.start()
        time.sleep(0.01)
        record = t.stop()
        assert record.elapsed == pytest.approx(record.ended_at - record.started_at, abs=1e-3)

    def test_can_reuse_timer(self):
        t = Timer("op")
        t.start()
        t.stop()
        t.start()
        record = t.stop()
        assert record.elapsed >= 0


class TestTimerRegistry:
    def test_get_or_create(self):
        reg = TimerRegistry()
        t = reg.get_or_create("op")
        assert isinstance(t, Timer)

    def test_get_or_create_same_instance(self):
        reg = TimerRegistry()
        t1 = reg.get_or_create("op")
        t2 = reg.get_or_create("op")
        assert t1 is t2

    def test_record_adds_to_store(self):
        store = MetricsStore()
        reg = TimerRegistry(store=store)
        reg.record("op", 0.5)
        assert len(store.get_series("op")) == 1

    def test_summary_empty(self):
        reg = TimerRegistry()
        assert reg.summary() == {}

    def test_summary_with_records(self):
        reg = TimerRegistry()
        reg.record("op", 1.0)
        reg.record("op", 3.0)
        s = reg.summary()
        assert "op" in s
        assert s["op"] == pytest.approx(2.0)

    def test_default_store_created(self):
        reg = TimerRegistry()
        reg.record("x", 1.0)
        s = reg.summary()
        assert "x" in s

    def test_shared_store_with_timer(self):
        store = MetricsStore()
        reg = TimerRegistry(store=store)
        t = reg.get_or_create("fast")
        t.start()
        t.stop()
        assert len(store.get_series("fast")) == 1
