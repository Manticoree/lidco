"""
Recovery Planner -- DR plan generation with RTO/RPO targets, runbook,
dependency ordering, and validation.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlanStatus(Enum):
    """Status of a DR plan."""

    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    EXPIRED = "expired"


class ComponentTier(Enum):
    """Criticality tier for a component."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Component:
    """A recoverable component in the DR plan."""

    name: str
    tier: ComponentTier
    rto_seconds: int = 3600
    rpo_seconds: int = 900
    dependencies: list[str] = field(default_factory=list)
    recovery_steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.rto_seconds < 0:
            raise ValueError("rto_seconds must be >= 0")
        if self.rpo_seconds < 0:
            raise ValueError("rpo_seconds must be >= 0")
        if not self.name:
            raise ValueError("name must not be empty")


@dataclass
class RunbookStep:
    """A single step in the recovery runbook."""

    order: int
    description: str
    component: str
    estimated_seconds: int = 60
    is_automated: bool = False
    validation_command: str = ""

    def __post_init__(self) -> None:
        if self.order < 0:
            raise ValueError("order must be >= 0")
        if not self.description:
            raise ValueError("description must not be empty")


@dataclass
class DRPlan:
    """A complete disaster recovery plan."""

    plan_id: str
    name: str
    status: PlanStatus
    components: list[Component] = field(default_factory=list)
    runbook: list[RunbookStep] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    target_rto_seconds: int = 3600
    target_rpo_seconds: int = 900
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_estimated_seconds(self) -> int:
        return sum(s.estimated_seconds for s in self.runbook)

    @property
    def meets_rto(self) -> bool:
        return self.total_estimated_seconds <= self.target_rto_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "status": self.status.value,
            "components": [
                {
                    "name": c.name,
                    "tier": c.tier.value,
                    "rto_seconds": c.rto_seconds,
                    "rpo_seconds": c.rpo_seconds,
                    "dependencies": c.dependencies,
                    "recovery_steps": c.recovery_steps,
                }
                for c in self.components
            ],
            "runbook_steps": len(self.runbook),
            "target_rto_seconds": self.target_rto_seconds,
            "target_rpo_seconds": self.target_rpo_seconds,
            "total_estimated_seconds": self.total_estimated_seconds,
            "meets_rto": self.meets_rto,
        }


class RecoveryPlanner:
    """Generates and validates DR plans with dependency ordering."""

    def __init__(self) -> None:
        self._components: dict[str, Component] = {}
        self._plans: dict[str, DRPlan] = {}

    def add_component(self, component: Component) -> None:
        """Register a component for DR planning."""
        self._components[component.name] = component

    def remove_component(self, name: str) -> bool:
        """Remove a registered component."""
        if name in self._components:
            del self._components[name]
            return True
        return False

    @property
    def components(self) -> dict[str, Component]:
        return dict(self._components)

    def generate_plan(
        self,
        name: str,
        target_rto: int = 3600,
        target_rpo: int = 900,
    ) -> DRPlan:
        """Generate a DR plan with ordered runbook from registered components."""
        plan_id = uuid.uuid4().hex[:12]
        now = time.time()

        ordered = self._dependency_order()

        runbook: list[RunbookStep] = []
        step_order = 0
        for comp_name in ordered:
            comp = self._components[comp_name]
            for step_desc in comp.recovery_steps:
                runbook.append(
                    RunbookStep(
                        order=step_order,
                        description=step_desc,
                        component=comp_name,
                        estimated_seconds=60,
                        is_automated=False,
                    )
                )
                step_order += 1

            if not comp.recovery_steps:
                runbook.append(
                    RunbookStep(
                        order=step_order,
                        description=f"Recover {comp_name}",
                        component=comp_name,
                        estimated_seconds=comp.rto_seconds // max(len(ordered), 1),
                        is_automated=False,
                    )
                )
                step_order += 1

        plan = DRPlan(
            plan_id=plan_id,
            name=name,
            status=PlanStatus.DRAFT,
            components=list(self._components.values()),
            runbook=runbook,
            created_at=now,
            updated_at=now,
            target_rto_seconds=target_rto,
            target_rpo_seconds=target_rpo,
        )

        self._plans[plan_id] = plan
        return plan

    def validate_plan(self, plan_id: str) -> list[str]:
        """Validate a DR plan, returning a list of issues found."""
        plan = self._plans.get(plan_id)
        if plan is None:
            return [f"Plan not found: {plan_id}"]

        issues: list[str] = []

        if not plan.components:
            issues.append("Plan has no components")

        if not plan.runbook:
            issues.append("Plan has no runbook steps")

        if not plan.meets_rto:
            issues.append(
                f"Estimated recovery ({plan.total_estimated_seconds}s) "
                f"exceeds RTO target ({plan.target_rto_seconds}s)"
            )

        for comp in plan.components:
            for dep in comp.dependencies:
                if dep not in self._components:
                    issues.append(
                        f"Component '{comp.name}' depends on unknown '{dep}'"
                    )

        if self._has_cycle():
            issues.append("Circular dependency detected among components")

        if not issues:
            plan.status = PlanStatus.VALIDATED

        return issues

    def activate_plan(self, plan_id: str) -> bool:
        """Mark a validated plan as active."""
        plan = self._plans.get(plan_id)
        if plan is None:
            return False
        if plan.status not in (PlanStatus.VALIDATED, PlanStatus.ACTIVE):
            return False
        plan.status = PlanStatus.ACTIVE
        plan.updated_at = time.time()
        return True

    def get_plan(self, plan_id: str) -> DRPlan | None:
        return self._plans.get(plan_id)

    def list_plans(self) -> list[DRPlan]:
        return list(self._plans.values())

    def _dependency_order(self) -> list[str]:
        """Topological sort of components by dependencies."""
        visited: set[str] = set()
        result: list[str] = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            comp = self._components.get(name)
            if comp:
                for dep in comp.dependencies:
                    if dep in self._components:
                        visit(dep)
            result.append(name)

        for name in self._components:
            visit(name)
        return result

    def _has_cycle(self) -> bool:
        """Check for cycles in component dependency graph."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in self._components}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            comp = self._components.get(node)
            if comp:
                for dep in comp.dependencies:
                    if dep in color:
                        if color[dep] == GRAY:
                            return True
                        if color[dep] == WHITE and dfs(dep):
                            return True
            color[node] = BLACK
            return False

        for node in self._components:
            if color[node] == WHITE:
                if dfs(node):
                    return True
        return False
