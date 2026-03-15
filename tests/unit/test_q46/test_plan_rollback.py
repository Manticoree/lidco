"""Tests for PlanRollbackTracker — Task 319."""

from __future__ import annotations

import pytest

from lidco.ai.plan_rollback import PlanCheckpoint, PlanRollbackTracker, RollbackError


# ---------------------------------------------------------------------------
# checkpoint()
# ---------------------------------------------------------------------------

class TestPlanRollbackCheckpoint:
    def test_checkpoint_increments_step(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("step 1")
        tracker.checkpoint("step 2")
        assert tracker.current_step == 2

    def test_checkpoint_stores_state(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("step 1", state={"files": ["auth.py"]})
        cp = tracker.current_checkpoint()
        assert cp.state == {"files": ["auth.py"]}

    def test_checkpoint_returns_object(self):
        tracker = PlanRollbackTracker()
        cp = tracker.checkpoint("my step")
        assert isinstance(cp, PlanCheckpoint)
        assert cp.label == "my step"

    def test_count_increases(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("a")
        tracker.checkpoint("b")
        assert tracker.count() == 2

    def test_max_checkpoints_respected(self):
        tracker = PlanRollbackTracker(max_checkpoints=3)
        for i in range(5):
            tracker.checkpoint(f"step {i}")
        assert tracker.count() == 3

    def test_oldest_dropped_when_full(self):
        tracker = PlanRollbackTracker(max_checkpoints=2)
        tracker.checkpoint("first")
        tracker.checkpoint("second")
        tracker.checkpoint("third")
        labels = [cp.label for cp in tracker.list_checkpoints()]
        assert "first" not in labels
        assert "third" in labels


# ---------------------------------------------------------------------------
# rollback()
# ---------------------------------------------------------------------------

class TestPlanRollbackRollback:
    def test_rollback_one_step(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("step 1")
        tracker.checkpoint("step 2")
        cp = tracker.rollback()
        assert cp.label == "step 1"

    def test_rollback_removes_checkpoint(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("step 1")
        tracker.checkpoint("step 2")
        tracker.rollback()
        assert tracker.count() == 1

    def test_rollback_no_checkpoints_raises(self):
        tracker = PlanRollbackTracker()
        with pytest.raises(RollbackError):
            tracker.rollback()

    def test_rollback_too_many_raises(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("step 1")
        with pytest.raises(RollbackError):
            tracker.rollback(steps=5)

    def test_rollback_updates_current_step(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("step 1")  # step 0
        tracker.checkpoint("step 2")  # step 1
        tracker.rollback()
        assert tracker.current_step == 0

    def test_rollback_multiple_steps(self):
        tracker = PlanRollbackTracker()
        for i in range(5):
            tracker.checkpoint(f"step {i}")
        tracker.rollback(steps=3)
        assert tracker.count() == 2


# ---------------------------------------------------------------------------
# rollback_to()
# ---------------------------------------------------------------------------

class TestPlanRollbackRollbackTo:
    def test_rollback_to_label(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("phase-1")
        tracker.checkpoint("phase-2")
        tracker.checkpoint("phase-3")
        cp = tracker.rollback_to("phase-1")
        assert cp.label == "phase-1"
        assert tracker.count() == 1

    def test_rollback_to_missing_label_raises(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("step 1")
        with pytest.raises(RollbackError):
            tracker.rollback_to("nonexistent")

    def test_rollback_to_most_recent_of_duplicate_labels(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("phase-1")
        tracker.checkpoint("phase-1")  # duplicate
        tracker.checkpoint("phase-2")
        cp = tracker.rollback_to("phase-1")
        # Should land on the second "phase-1" (most recent)
        assert cp.label == "phase-1"
        assert tracker.count() == 2


# ---------------------------------------------------------------------------
# clear() / current_checkpoint()
# ---------------------------------------------------------------------------

class TestPlanRollbackOther:
    def test_current_checkpoint_none_when_empty(self):
        tracker = PlanRollbackTracker()
        assert tracker.current_checkpoint() is None

    def test_current_checkpoint_returns_latest(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("first")
        tracker.checkpoint("last")
        assert tracker.current_checkpoint().label == "last"

    def test_clear_resets_all(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("x")
        tracker.checkpoint("y")
        tracker.clear()
        assert tracker.count() == 0
        assert tracker.current_step == 0

    def test_list_checkpoints(self):
        tracker = PlanRollbackTracker()
        tracker.checkpoint("a")
        tracker.checkpoint("b")
        labels = [cp.label for cp in tracker.list_checkpoints()]
        assert labels == ["a", "b"]
