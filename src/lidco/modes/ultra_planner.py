"""Multi-pass planning with critique rounds."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PlanPhase(str, Enum):
    """Phases in the ultra-planning lifecycle."""

    GATHER = "gather"
    PLAN = "plan"
    CRITIQUE = "critique"
    REVISE = "revise"
    FINALIZE = "finalize"


@dataclass(frozen=True)
class PlanSection:
    """A single section within an UltraPlan."""

    title: str
    content: str
    phase: PlanPhase = PlanPhase.PLAN
    confidence: float = 0.5


@dataclass(frozen=True)
class UltraPlan:
    """Immutable multi-pass plan."""

    title: str
    sections: tuple[PlanSection, ...] = ()
    risks: tuple[str, ...] = ()
    checklist: tuple[str, ...] = ()
    passes: int = 0


class UltraPlanner:
    """Multi-pass planner with critique rounds."""

    def __init__(self, max_passes: int = 3) -> None:
        self._max_passes = max_passes

    def create_plan(self, title: str, description: str) -> UltraPlan:
        """Generate an initial plan from a description."""
        sections: list[PlanSection] = []
        if description:
            sections.append(PlanSection(
                title="Overview",
                content=description,
                phase=PlanPhase.GATHER,
                confidence=0.5,
            ))
            sections.append(PlanSection(
                title="Implementation",
                content=f"Implement: {description}",
                phase=PlanPhase.PLAN,
                confidence=0.5,
            ))
        return UltraPlan(title=title, sections=tuple(sections), passes=1)

    def add_section(self, plan: UltraPlan, title: str, content: str) -> UltraPlan:
        """Return a new plan with an additional section."""
        new_section = PlanSection(title=title, content=content)
        return UltraPlan(
            title=plan.title,
            sections=(*plan.sections, new_section),
            risks=plan.risks,
            checklist=plan.checklist,
            passes=plan.passes,
        )

    def critique(self, plan: UltraPlan) -> list[str]:
        """Identify weak areas in the plan."""
        issues: list[str] = []
        for sec in plan.sections:
            if len(sec.content) < 20:
                issues.append(f"Section '{sec.title}' has short content.")
            if sec.confidence < 0.3:
                issues.append(f"Section '{sec.title}' has low confidence ({sec.confidence}).")
        titles = {s.title.lower() for s in plan.sections}
        if not any("risk" in t for t in titles):
            issues.append("Missing risk assessment section.")
        if not any("test" in t for t in titles):
            issues.append("Missing testing plan section.")
        if not plan.checklist:
            issues.append("Checklist is empty.")
        return issues

    def revise(self, plan: UltraPlan, feedback: list[str]) -> UltraPlan:
        """Incorporate critique feedback and increment pass count."""
        new_risks = (*plan.risks, *feedback)
        return UltraPlan(
            title=plan.title,
            sections=plan.sections,
            risks=new_risks,
            checklist=plan.checklist,
            passes=plan.passes + 1,
        )

    def add_risk(self, plan: UltraPlan, risk: str) -> UltraPlan:
        """Return a new plan with an additional risk."""
        return UltraPlan(
            title=plan.title,
            sections=plan.sections,
            risks=(*plan.risks, risk),
            checklist=plan.checklist,
            passes=plan.passes,
        )

    def add_checklist_item(self, plan: UltraPlan, item: str) -> UltraPlan:
        """Return a new plan with an additional checklist item."""
        return UltraPlan(
            title=plan.title,
            sections=plan.sections,
            risks=plan.risks,
            checklist=(*plan.checklist, item),
            passes=plan.passes,
        )

    def to_markdown(self, plan: UltraPlan) -> str:
        """Format plan as markdown."""
        lines: list[str] = [f"# {plan.title}", ""]
        for sec in plan.sections:
            lines.append(f"## {sec.title}")
            lines.append(sec.content)
            lines.append("")
        if plan.risks:
            lines.append("## Risks")
            for r in plan.risks:
                lines.append(f"- {r}")
            lines.append("")
        if plan.checklist:
            lines.append("## Checklist")
            for item in plan.checklist:
                lines.append(f"- [ ] {item}")
            lines.append("")
        return "\n".join(lines)

    def summary(self, plan: UltraPlan) -> str:
        """One-line summary of the plan."""
        return (
            f"Plan '{plan.title}': {len(plan.sections)} sections, "
            f"{len(plan.risks)} risks, {len(plan.checklist)} checklist items, "
            f"{plan.passes} pass(es)"
        )
