"""Tests for src/lidco/memory/consolidation_scheduler.py."""
import asyncio
import threading
import time
from dataclasses import dataclass
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


# Minimal fake ConsolidationReport
@dataclass
class FakeReport:
    original_count: int = 5
    consolidated_count: int = 3
    merged_groups: int = 1
    removed_stale: int = 1
    summary: str = "test report"


class FakeConsolidator:
    """Fake MemoryConsolidator for testing."""
    def __init__(self, report=None, error=None):
        self._report = report or FakeReport()
        self._error = error
        self.call_count = 0

    def consolidate(self, store=None):
        self.call_count += 1
        if self._error:
            raise self._error
        return self._report


class FakeEventBus:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


class FakeStore:
    pass


class TestConsolidationJob:
    def test_default_idle(self):
        from lidco.memory.consolidation_scheduler import ConsolidationJob
        job = ConsolidationJob(status="idle")
        assert job.status == "idle"
        assert job.last_run is None
        assert job.last_report is None
        assert job.run_count == 0
        assert job.error == ""

    def test_fields(self):
        from lidco.memory.consolidation_scheduler import ConsolidationJob
        job = ConsolidationJob(status="completed", last_run=1000.0, run_count=3, error="x")
        assert job.status == "completed"
        assert job.last_run == 1000.0
        assert job.run_count == 3
        assert job.error == "x"


class TestAsyncConsolidationSchedulerRunOnce:
    def test_run_once_success(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        report = FakeReport(original_count=10, consolidated_count=7)
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator(report=report))
        job = sched.run_once()
        assert job.status == "completed"
        assert job.run_count == 1
        assert job.last_report is report
        assert job.last_run is not None
        assert job.error == ""

    def test_run_once_with_store(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        consolidator = FakeConsolidator()
        sched = AsyncConsolidationScheduler(consolidator=consolidator)
        store = FakeStore()
        job = sched.run_once(store=store)
        assert job.status == "completed"
        assert consolidator.call_count == 1

    def test_run_once_failure(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        consolidator = FakeConsolidator(error=RuntimeError("boom"))
        sched = AsyncConsolidationScheduler(consolidator=consolidator)
        job = sched.run_once()
        assert job.status == "failed"
        assert "boom" in job.error
        assert job.run_count == 1

    def test_run_once_increments_count(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator())
        sched.run_once()
        sched.run_once()
        sched.run_once()
        assert sched.get_job().run_count == 3

    def test_run_once_updates_last_run_timestamp(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator())
        before = time.time()
        sched.run_once()
        after = time.time()
        assert before <= sched.get_job().last_run <= after

    def test_run_once_no_consolidator(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=None)
        job = sched.run_once()
        assert job.status == "failed"
        assert job.error != ""

    def test_run_once_with_event_bus(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        bus = FakeEventBus()
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator(), event_bus=bus)
        sched.run_once()
        assert len(bus.events) == 1

    def test_run_once_failure_no_event(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        bus = FakeEventBus()
        consolidator = FakeConsolidator(error=ValueError("bad"))
        sched = AsyncConsolidationScheduler(consolidator=consolidator, event_bus=bus)
        sched.run_once()
        assert len(bus.events) == 0


class TestAsyncConsolidationSchedulerGetJob:
    def test_get_job_initial(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator())
        job = sched.get_job()
        assert job.status == "idle"

    def test_is_running_false_initially(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator())
        assert sched.is_running is False


class TestAsyncConsolidationSchedulerScheduleCancel:
    def test_schedule_starts_thread(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator())
        sched.schedule(interval_s=0.05)
        assert sched.is_running is True
        time.sleep(0.15)
        sched.cancel()
        assert sched.is_running is False
        assert sched.get_job().run_count >= 1

    def test_cancel_when_not_running(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator())
        sched.cancel()  # should not raise
        assert sched.is_running is False

    def test_schedule_replaces_existing(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator())
        sched.schedule(interval_s=10.0)
        assert sched.is_running is True
        sched.schedule(interval_s=10.0)  # replace
        assert sched.is_running is True
        sched.cancel()

    def test_schedule_with_store(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        consolidator = FakeConsolidator()
        sched = AsyncConsolidationScheduler(consolidator=consolidator)
        sched.schedule(store=FakeStore(), interval_s=0.05)
        time.sleep(0.15)
        sched.cancel()
        assert consolidator.call_count >= 1

    def test_schedule_daemon_thread(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator())
        sched.schedule(interval_s=10.0)
        assert sched._thread.daemon is True
        sched.cancel()

    def test_schedule_error_continues(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        # Even if consolidator errors, the thread keeps running
        consolidator = FakeConsolidator(error=RuntimeError("fail"))
        sched = AsyncConsolidationScheduler(consolidator=consolidator)
        sched.schedule(interval_s=0.05)
        time.sleep(0.15)
        sched.cancel()
        assert sched.get_job().run_count >= 1
        assert sched.get_job().status == "failed"

    def test_job_status_running_during_schedule(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator())
        sched.schedule(interval_s=0.05)
        time.sleep(0.15)
        sched.cancel()
        # After cancel, status reflects last run result
        assert sched.get_job().status in ("completed", "failed")

    def test_multiple_cancel_safe(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator())
        sched.schedule(interval_s=0.05)
        sched.cancel()
        sched.cancel()
        sched.cancel()
        assert sched.is_running is False

    def test_run_once_after_cancel(self):
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler
        sched = AsyncConsolidationScheduler(consolidator=FakeConsolidator())
        sched.schedule(interval_s=0.05)
        time.sleep(0.1)
        sched.cancel()
        count_before = sched.get_job().run_count
        sched.run_once()
        assert sched.get_job().run_count == count_before + 1
