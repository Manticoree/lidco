"""TodoPlanningAgent — decompose prompts into todo plans (stdlib only)."""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

from lidco.tasks.live_todo import TodoItem, TodoStatus


@dataclass
class TodoPlan:
    id: str
    description: str
    items: list[TodoItem] = field(default_factory=list)

    def to_dag(self) -> dict[str, TodoItem]:
        """Return ordered dict {id: TodoItem} respecting depends_on edges."""
        result: dict[str, TodoItem] = {}
        for item in self.items:
            result[item.id] = item
        return result


_HIGH_KEYWORDS = {"refactor", "architecture", "redesign", "migrate", "rewrite", "complex", "entire", "overhaul"}
_LOW_KEYWORDS = {"fix", "typo", "rename", "update", "bump", "minor", "small", "simple", "trivial"}


class TodoPlanningAgent:
    """Decompose natural-language prompts into structured TodoPlan objects."""

    def __init__(self, event_bus=None) -> None:
        self._event_bus = event_bus

    def plan(self, prompt: str, llm_fn: Optional[Callable[[str], str]] = None) -> TodoPlan:
        plan_id = uuid.uuid4().hex[:12]
        description = prompt.strip() if prompt.strip() else "Unnamed plan"

        items: list[TodoItem] | None = None

        # Try LLM if provided
        if llm_fn is not None:
            items = self._try_llm(prompt, llm_fn)

        # Heuristic fallback
        if items is None:
            items = self._heuristic_parse(prompt)

        plan = TodoPlan(id=plan_id, description=description, items=items)

        if self._event_bus is not None:
            self._event_bus.publish("plan.created", {"plan_id": plan_id, "item_count": len(items)})

        return plan

    def _try_llm(self, prompt: str, llm_fn: Callable[[str], str]) -> list[TodoItem] | None:
        try:
            planning_prompt = (
                f"Break down the following task into steps. "
                f"Return JSON with an 'items' array, each item having 'id', 'label', "
                f"and optional 'depends_on' (list of ids).\n\nTask: {prompt}"
            )
            raw = llm_fn(planning_prompt)
            data = json.loads(raw)
            if "items" not in data:
                return None
            items: list[TodoItem] = []
            for entry in data["items"]:
                items.append(
                    TodoItem(
                        id=entry.get("id", uuid.uuid4().hex[:8]),
                        label=entry.get("label", ""),
                        depends_on=list(entry.get("depends_on", [])),
                    )
                )
            return items if items else None
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def _heuristic_parse(self, prompt: str) -> list[TodoItem]:
        lines = [ln.strip() for ln in prompt.strip().splitlines() if ln.strip()]

        # Try numbered steps: "1. ...", "1) ..."
        numbered: list[str] = []
        for ln in lines:
            m = re.match(r"^\d+[\.\)]\s*(.+)", ln)
            if m:
                numbered.append(m.group(1).strip())

        if numbered:
            return [
                TodoItem(id=f"step-{i+1}", label=label)
                for i, label in enumerate(numbered)
            ]

        # Multiple lines => each line is a step
        if len(lines) > 1:
            return [
                TodoItem(id=f"step-{i+1}", label=label)
                for i, label in enumerate(lines)
            ]

        # Single line or empty => 3 generic steps
        return [
            TodoItem(id="step-1", label="Research"),
            TodoItem(id="step-2", label="Implement"),
            TodoItem(id="step-3", label="Test"),
        ]

    def estimate_effort(self, plan: TodoPlan) -> dict[str, str]:
        result: dict[str, str] = {}
        for item in plan.items:
            words = set(item.label.lower().split())
            if words & _HIGH_KEYWORDS:
                result[item.id] = "high"
            elif words & _LOW_KEYWORDS:
                result[item.id] = "low"
            else:
                result[item.id] = "medium"
        return result
