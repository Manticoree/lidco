"""QuickActionRegistry — register context-sensitive actions with priority and shortcuts."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QuickAction:
    """A quick action definition."""

    name: str
    description: str
    handler_name: str
    priority: int = 0
    shortcut: str = ""
    context: str = "global"
    enabled: bool = True


@dataclass(frozen=True)
class ActionResult:
    """Result of executing a quick action."""

    action_name: str
    success: bool
    message: str
    preview: str = ""


class QuickActionRegistry:
    """Registry for context-sensitive quick actions."""

    def __init__(self) -> None:
        self._actions: dict[str, QuickAction] = {}

    def register(self, action: QuickAction) -> QuickAction:
        """Register *action* and return it."""
        self._actions[action.name] = action
        return action

    def unregister(self, name: str) -> bool:
        """Remove action by *name*. Return ``True`` if it existed."""
        return self._actions.pop(name, None) is not None

    def get(self, name: str) -> QuickAction | None:
        """Look up an action by *name*."""
        return self._actions.get(name)

    def find(self, context: str = "global") -> list[QuickAction]:
        """Return actions matching *context*, sorted by priority descending."""
        return sorted(
            [a for a in self._actions.values() if a.context == context and a.enabled],
            key=lambda a: a.priority,
            reverse=True,
        )

    def execute(self, name: str, **kwargs: object) -> ActionResult:
        """Simulate execution of action *name*."""
        action = self._actions.get(name)
        if action is None:
            return ActionResult(
                action_name=name,
                success=False,
                message=f"Action '{name}' not found",
            )
        if not action.enabled:
            return ActionResult(
                action_name=name,
                success=False,
                message=f"Action '{name}' is disabled",
            )
        return ActionResult(
            action_name=name,
            success=True,
            message=f"Executed '{name}' via handler '{action.handler_name}'",
            preview=f"handler={action.handler_name} kwargs={kwargs}",
        )

    def enable(self, name: str) -> bool:
        """Enable action *name*. Return ``True`` if found."""
        action = self._actions.get(name)
        if action is None:
            return False
        action.enabled = True
        return True

    def disable(self, name: str) -> bool:
        """Disable action *name*. Return ``True`` if found."""
        action = self._actions.get(name)
        if action is None:
            return False
        action.enabled = False
        return True

    def by_shortcut(self, shortcut: str) -> QuickAction | None:
        """Find the first action with the given *shortcut*."""
        for action in self._actions.values():
            if action.shortcut == shortcut:
                return action
        return None

    def all_actions(self) -> list[QuickAction]:
        """Return all registered actions."""
        return list(self._actions.values())

    def summary(self) -> dict:
        """Return a summary dict."""
        return {
            "total": len(self._actions),
            "enabled": sum(1 for a in self._actions.values() if a.enabled),
            "disabled": sum(1 for a in self._actions.values() if not a.enabled),
            "contexts": sorted({a.context for a in self._actions.values()}),
        }
