"""UI automation script recording and replay."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from lidco.computer_use.controller import ScreenController


@dataclass(frozen=True)
class AutomationAction:
    """A single recorded automation action."""

    action_type: str
    params: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    description: str = ""


@dataclass(frozen=True)
class AutomationScript:
    """A named sequence of automation actions."""

    name: str
    actions: tuple[AutomationAction, ...] = ()
    created_at: float = 0.0


class AutomationRunner:
    """Records and replays UI automation scripts."""

    def __init__(self, controller: ScreenController | None = None) -> None:
        self._controller = controller or ScreenController()
        self._recorded: list[AutomationAction] = []

    def record_action(
        self,
        action_type: str,
        params: dict[str, Any] | None = None,
        description: str = "",
    ) -> AutomationAction:
        """Record a single automation action."""
        action = AutomationAction(
            action_type=action_type,
            params=params or {},
            timestamp=time.time(),
            description=description,
        )
        self._recorded.append(action)
        return action

    def create_script(self, name: str) -> AutomationScript:
        """Create a script from all recorded actions."""
        script = AutomationScript(
            name=name,
            actions=tuple(self._recorded),
            created_at=time.time(),
        )
        return script

    def replay(self, script: AutomationScript) -> list[dict[str, Any]]:
        """Replay a script against the controller, returning per-action results."""
        results: list[dict[str, Any]] = []
        for action in script.actions:
            result: dict[str, Any] = {
                "action_type": action.action_type,
                "description": action.description,
                "status": "ok",
            }
            atype = action.action_type
            p = action.params

            if atype == "move":
                coord = self._controller.move(p.get("x", 0), p.get("y", 0))
                result["position"] = (coord.x, coord.y)
            elif atype == "click":
                coord = self._controller.click(
                    p.get("x", 0), p.get("y", 0), p.get("button", "left")
                )
                result["position"] = (coord.x, coord.y)
            elif atype == "double_click":
                coord = self._controller.double_click(p.get("x", 0), p.get("y", 0))
                result["position"] = (coord.x, coord.y)
            elif atype == "type_text":
                text = self._controller.type_text(p.get("text", ""))
                result["text"] = text
            elif atype == "hotkey":
                keys = p.get("keys", [])
                combo = self._controller.hotkey(*keys)
                result["combo"] = combo
            elif atype == "drag":
                start, end = self._controller.drag(
                    p.get("from_x", 0),
                    p.get("from_y", 0),
                    p.get("to_x", 0),
                    p.get("to_y", 0),
                )
                result["from"] = (start.x, start.y)
                result["to"] = (end.x, end.y)
            else:
                result["status"] = "unknown_action"

            results.append(result)
        return results

    def clear_recording(self) -> None:
        """Clear all recorded actions."""
        self._recorded.clear()

    def recorded_actions(self) -> list[AutomationAction]:
        """Return a copy of recorded actions."""
        return list(self._recorded)
