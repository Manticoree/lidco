"""Tests for lidco.agents.cancellation."""
from __future__ import annotations

import pytest

from lidco.agents.cancellation import (
    CancelReason,
    CancelRecord,
    CancellationManager,
)


class TestCancelRecord:
    def test_frozen(self) -> None:
        r = CancelRecord(agent_id="a", reason=CancelReason.TIMEOUT)
        with pytest.raises(AttributeError):
            r.agent_id = "b"  # type: ignore[misc]

    def test_defaults(self) -> None:
        r = CancelRecord(agent_id="a", reason=CancelReason.USER_REQUEST)
        assert r.cascade_from == ""
        assert r.timestamp > 0


class TestCancellationManager:
    def test_cancel(self) -> None:
        mgr = CancellationManager()
        rec = mgr.cancel("agent1", CancelReason.TIMEOUT)
        assert rec.agent_id == "agent1"
        assert rec.reason == CancelReason.TIMEOUT
        assert mgr.is_cancelled("agent1")

    def test_not_cancelled(self) -> None:
        mgr = CancellationManager()
        assert not mgr.is_cancelled("agent1")

    def test_cascade_cancel(self) -> None:
        mgr = CancellationManager()
        records = mgr.cascade_cancel("root", ["dep1", "dep2"])
        assert len(records) == 3
        assert records[0].reason == CancelReason.USER_REQUEST
        assert records[1].reason == CancelReason.CASCADE
        assert records[1].cascade_from == "root"
        assert records[2].cascade_from == "root"
        assert mgr.is_cancelled("root")
        assert mgr.is_cancelled("dep1")
        assert mgr.is_cancelled("dep2")

    def test_get_cancelled(self) -> None:
        mgr = CancellationManager()
        mgr.cancel("a")
        mgr.cancel("b", CancelReason.BUDGET_EXCEEDED)
        cancelled = mgr.get_cancelled()
        assert len(cancelled) == 2

    def test_clear(self) -> None:
        mgr = CancellationManager()
        mgr.cancel("a")
        mgr.clear()
        assert not mgr.is_cancelled("a")
        assert mgr.get_cancelled() == []

    def test_grace_period(self) -> None:
        mgr = CancellationManager(grace_period=10.0)
        assert mgr.grace_period == 10.0

    def test_summary_empty(self) -> None:
        mgr = CancellationManager()
        assert "No cancellations" in mgr.summary()

    def test_summary_with_records(self) -> None:
        mgr = CancellationManager()
        mgr.cancel("agent1", CancelReason.TIMEOUT)
        s = mgr.summary()
        assert "1" in s
        assert "agent1" in s
