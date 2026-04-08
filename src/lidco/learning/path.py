"""Learning Path -- personalized paths based on skill gaps, project needs, resources."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Resource:
    """A recommended learning resource."""

    title: str
    url: str = ""
    kind: str = "article"  # article, video, tutorial, book, exercise
    estimated_minutes: int = 30


@dataclass
class PathStep:
    """One step in a learning path."""

    title: str
    skill: str
    description: str = ""
    resources: list[Resource] = field(default_factory=list)
    completed: bool = False

    def complete(self) -> PathStep:
        return PathStep(
            title=self.title,
            skill=self.skill,
            description=self.description,
            resources=list(self.resources),
            completed=True,
        )


@dataclass
class LearningPath:
    """A sequence of steps for skill development."""

    name: str
    steps: list[PathStep] = field(default_factory=list)
    target_skills: list[str] = field(default_factory=list)

    def add_step(self, step: PathStep) -> None:
        self.steps.append(step)

    def complete_step(self, index: int) -> None:
        if 0 <= index < len(self.steps):
            self.steps[index] = self.steps[index].complete()

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        return sum(1 for s in self.steps if s.completed) / len(self.steps)

    @property
    def completed_count(self) -> int:
        return sum(1 for s in self.steps if s.completed)

    def next_step(self) -> PathStep | None:
        for s in self.steps:
            if not s.completed:
                return s
        return None


class LearningPathGenerator:
    """Generate personalized learning paths from skill gaps."""

    def __init__(self) -> None:
        self._templates: dict[str, list[dict[str, Any]]] = {}

    def register_template(self, skill: str, steps: list[dict[str, Any]]) -> None:
        self._templates[skill] = steps

    def generate(
        self,
        weak_skills: list[str],
        project_needs: list[str] | None = None,
    ) -> LearningPath:
        needs = set(weak_skills)
        if project_needs:
            needs.update(project_needs)

        path = LearningPath(name="Personalized Path", target_skills=sorted(needs))

        for skill in sorted(needs):
            template = self._templates.get(skill, [])
            if template:
                for step_def in template:
                    resources = [
                        Resource(title=r.get("title", ""), url=r.get("url", ""), kind=r.get("kind", "article"))
                        for r in step_def.get("resources", [])
                    ]
                    path.add_step(
                        PathStep(
                            title=step_def.get("title", f"Learn {skill}"),
                            skill=skill,
                            description=step_def.get("description", ""),
                            resources=resources,
                        )
                    )
            else:
                path.add_step(
                    PathStep(
                        title=f"Learn {skill}",
                        skill=skill,
                        description=f"Study and practice {skill}.",
                        resources=[Resource(title=f"{skill} documentation")],
                    )
                )

        return path

    def format_path(self, path: LearningPath) -> str:
        if not path.steps:
            return f"Path '{path.name}': no steps."
        lines = [f"Path '{path.name}' ({path.progress:.0%} complete):"]
        for i, step in enumerate(path.steps):
            mark = "[x]" if step.completed else "[ ]"
            lines.append(f"  {i + 1}. {mark} {step.title} ({step.skill})")
            for r in step.resources:
                lines.append(f"       - {r.title} ({r.kind})")
        return "\n".join(lines)
