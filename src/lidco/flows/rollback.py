"""Rollback helpers for flows."""
from __future__ import annotations

from .checkpoint import FlowCheckpointManager
from .engine import Flow, FlowStep, StepStatus


def rollback_to_step(
    flow: Flow,
    step_index: int,
    checkpoint_manager: FlowCheckpointManager,
) -> bool:
    """Rollback files to checkpoint of given step and reset later steps to pending."""
    target_step = next((s for s in flow.steps if s.index == step_index), None)
    if target_step is None or target_step.checkpoint_id is None:
        return False

    success = checkpoint_manager.rollback(target_step.checkpoint_id)
    if not success:
        return False

    # Reset all steps from target onward to pending
    for step in flow.steps:
        if step.index >= step_index:
            step.status = StepStatus.PENDING
            step.error = None
            step.result = None

    return True
