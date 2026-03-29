"""LiveTodoTracker — real-time todo board with event bus integration (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TodoStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    BLOCKED = "blocked"


@dataclass
class TodoItem:
    id: str
    label: str
    status: TodoStatus = TodoStatus.PENDING
    blocked_reason: Optional[str] = None
    depends_on: list[str] = field(default_factory=list)


@dataclass
class TodoBoardState:
    items: list[TodoItem]

    @property
    def pending(self) -> list[TodoItem]:
        return [i for i in self.items if i.status == TodoStatus.PENDING]

    @property
    def active(self) -> list[TodoItem]:
        return [i for i in self.items if i.status == TodoStatus.ACTIVE]

    @property
    def done(self) -> list[TodoItem]:
        return [i for i in self.items if i.status == TodoStatus.DONE]

    @property
    def blocked(self) -> list[TodoItem]:
        return [i for i in self.items if i.status == TodoStatus.BLOCKED]


_STATUS_ICONS = {
    TodoStatus.PENDING: "[ ]",
    TodoStatus.ACTIVE: "[>]",
    TodoStatus.DONE: "[x]",
    TodoStatus.BLOCKED: "[!]",
}


class LiveTodoTracker:
    """Real-time todo board that optionally publishes updates via an EventBus."""

    def __init__(self, event_bus=None) -> None:
        self._items: list[TodoItem] = []
        self._event_bus = event_bus

    def add_item(self, item: TodoItem) -> None:
        self._items = [*self._items, item]

    def update(self, item_id: str, status: TodoStatus, blocked_reason: str | None = None) -> None:
        found = False
        new_items: list[TodoItem] = []
        for item in self._items:
            if item.id == item_id:
                found = True
                new_items.append(
                    TodoItem(
                        id=item.id,
                        label=item.label,
                        status=status,
                        blocked_reason=blocked_reason if status == TodoStatus.BLOCKED else item.blocked_reason,
                        depends_on=list(item.depends_on),
                    )
                )
            else:
                new_items.append(item)
        if not found:
            raise KeyError(f"Item not found: {item_id}")
        self._items = new_items
        if self._event_bus is not None:
            self._event_bus.publish("todo.updated", {"item_id": item_id, "status": status.value})

    def render_ascii(self) -> str:
        if not self._items:
            return ""
        lines: list[str] = []
        for item in self._items:
            icon = _STATUS_ICONS.get(item.status, "[ ]")
            suffix = f" ({item.status.value})"
            if item.status == TodoStatus.BLOCKED and item.blocked_reason:
                suffix = f" (blocked: {item.blocked_reason})"
            lines.append(f"{icon} {item.label}{suffix}")
        return "\n".join(lines)

    def get_state(self) -> TodoBoardState:
        return TodoBoardState(items=list(self._items))

    def clear(self) -> None:
        self._items = []

    def from_plan(self, plan: list[dict]) -> None:
        self._items = []
        for entry in plan:
            self._items.append(
                TodoItem(
                    id=entry.get("id", ""),
                    label=entry.get("label", ""),
                    depends_on=list(entry.get("depends_on", [])),
                )
            )
