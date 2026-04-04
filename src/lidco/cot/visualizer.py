"""CoTVisualizer — visualize reasoning chains as tree/graph."""
from __future__ import annotations

from lidco.cot.planner import ReasoningStep, StepStatus


class CoTVisualizer:
    """Visualize reasoning chains in various formats."""

    def __init__(self) -> None:
        pass

    def as_text_tree(self, steps: list[ReasoningStep], indent: int = 2) -> str:
        """Render steps as indented text tree."""
        if not steps:
            return "(empty chain)"

        step_map = {s.step_id: s for s in steps}
        roots = [s for s in steps if not s.depends_on]
        children: dict[str, list[str]] = {}
        for s in steps:
            for dep in s.depends_on:
                children.setdefault(dep, []).append(s.step_id)

        lines: list[str] = []

        def render(sid: str, depth: int) -> None:
            step = step_map.get(sid)
            if not step:
                return
            prefix = " " * (depth * indent)
            status_icon = {
                StepStatus.PENDING: "[ ]",
                StepStatus.IN_PROGRESS: "[~]",
                StepStatus.COMPLETED: "[x]",
                StepStatus.FAILED: "[!]",
                StepStatus.SKIPPED: "[-]",
            }.get(step.status, "[ ]")
            lines.append(f"{prefix}{status_icon} {step.step_id}: {step.description}")
            for child_id in children.get(sid, []):
                render(child_id, depth + 1)

        for root in roots:
            render(root.step_id, 0)

        # Also include orphans (steps not reachable from roots)
        rendered_ids = set()
        for line in lines:
            for s in steps:
                if s.step_id in line:
                    rendered_ids.add(s.step_id)
        for s in steps:
            if s.step_id not in rendered_ids:
                lines.append(f"[ ] {s.step_id}: {s.description}")

        return "\n".join(lines)

    def as_mermaid(self, steps: list[ReasoningStep]) -> str:
        """Render steps as Mermaid graph."""
        if not steps:
            return "graph TD\n  empty[No steps]"

        lines = ["graph TD"]
        for step in steps:
            label = step.description[:40].replace('"', "'")
            shape = {
                StepStatus.COMPLETED: f'["{label}"]',
                StepStatus.FAILED: f'{{"{label}"}}',
                StepStatus.IN_PROGRESS: f'("{label}")',
            }.get(step.status, f'["{label}"]')
            lines.append(f"  {step.step_id}{shape}")

        for step in steps:
            for dep in step.depends_on:
                lines.append(f"  {dep} --> {step.step_id}")

        return "\n".join(lines)

    def as_json(self, steps: list[ReasoningStep]) -> list[dict]:
        """Render steps as JSON-serializable list."""
        return [
            {
                "id": s.step_id,
                "description": s.description,
                "status": s.status.value,
                "depends_on": s.depends_on,
                "result": s.result,
                "estimated_tokens": s.estimated_tokens,
            }
            for s in steps
        ]

    def critical_path(self, steps: list[ReasoningStep]) -> list[str]:
        """Find the longest dependency chain (critical path)."""
        step_map = {s.step_id: s for s in steps}
        memo: dict[str, int] = {}

        def longest(sid: str) -> int:
            if sid in memo:
                return memo[sid]
            step = step_map.get(sid)
            if not step or not step.depends_on:
                memo[sid] = 1
                return 1
            max_dep = max(longest(d) for d in step.depends_on if d in step_map)
            memo[sid] = max_dep + 1
            return memo[sid]

        if not steps:
            return []

        for s in steps:
            longest(s.step_id)

        # Reconstruct path from the step with highest depth
        if not memo:
            return []
        end_id = max(memo, key=memo.get)
        path = []
        current = end_id
        while current:
            path.append(current)
            step = step_map.get(current)
            if not step or not step.depends_on:
                break
            # Pick dependency with longest chain
            current = max(
                (d for d in step.depends_on if d in step_map),
                key=lambda d: memo.get(d, 0),
                default=None,
            )
        return list(reversed(path))

    def summary(self, steps: list[ReasoningStep]) -> dict:
        return {
            "total_steps": len(steps),
            "critical_path_length": len(self.critical_path(steps)),
            "completed": sum(1 for s in steps if s.status == StepStatus.COMPLETED),
            "pending": sum(1 for s in steps if s.status == StepStatus.PENDING),
        }
