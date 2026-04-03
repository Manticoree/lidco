"""Recovery management — plans, actions, post-incident reports."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RecoveryAction:
    """A single recovery action."""

    id: str
    incident_id: str
    action: str  # revert / rotate / restore / report
    target: str
    status: str = "pending"
    timestamp: float = 0.0


@dataclass
class RecoveryPlan:
    """A plan containing recovery actions."""

    incident_id: str
    actions: list[RecoveryAction] = field(default_factory=list)
    status: str = "draft"  # draft / approved / executing / completed


class RecoveryManager:
    """Manage incident recovery plans."""

    def __init__(self) -> None:
        self._plans: dict[str, RecoveryPlan] = {}

    def create_plan(self, incident_id: str) -> RecoveryPlan:
        """Create a new recovery plan for *incident_id*."""
        plan = RecoveryPlan(incident_id=incident_id)
        self._plans[incident_id] = plan
        return plan

    def add_action(self, incident_id: str, action: str, target: str) -> RecoveryAction:
        """Add an action to the plan for *incident_id*."""
        plan = self._plans.get(incident_id)
        if plan is None:
            plan = self.create_plan(incident_id)
        ra = RecoveryAction(
            id=uuid.uuid4().hex[:12],
            incident_id=incident_id,
            action=action,
            target=target,
            status="pending",
            timestamp=time.time(),
        )
        plan.actions.append(ra)
        return ra

    def execute_plan(self, incident_id: str) -> RecoveryPlan:
        """Execute the plan for *incident_id*."""
        plan = self._plans.get(incident_id)
        if plan is None:
            plan = self.create_plan(incident_id)
        plan.status = "executing"
        # Mark all actions as completed
        completed: list[RecoveryAction] = []
        for a in plan.actions:
            completed.append(
                RecoveryAction(
                    id=a.id,
                    incident_id=a.incident_id,
                    action=a.action,
                    target=a.target,
                    status="completed",
                    timestamp=a.timestamp,
                )
            )
        plan.actions = completed
        plan.status = "completed"
        return plan

    def get_plan(self, incident_id: str) -> RecoveryPlan | None:
        """Return the plan for *incident_id* or ``None``."""
        return self._plans.get(incident_id)

    def generate_report(self, incident_id: str) -> str:
        """Generate a post-incident report."""
        plan = self._plans.get(incident_id)
        if plan is None:
            return f"No recovery plan found for incident {incident_id}."
        lines = [
            f"Post-Incident Report: {incident_id}",
            f"Status: {plan.status}",
            f"Actions: {len(plan.actions)}",
        ]
        for a in plan.actions:
            lines.append(f"  - [{a.status}] {a.action} on {a.target}")
        return "\n".join(lines)

    def all_plans(self) -> list[RecoveryPlan]:
        """Return all plans."""
        return list(self._plans.values())

    def summary(self) -> dict:
        """Summary stats."""
        by_status: dict[str, int] = {}
        total_actions = 0
        for p in self._plans.values():
            by_status[p.status] = by_status.get(p.status, 0) + 1
            total_actions += len(p.actions)
        return {
            "total_plans": len(self._plans),
            "total_actions": total_actions,
            "by_status": by_status,
        }
