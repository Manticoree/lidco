"""Records every tool call and result as a typed Action-Observation trajectory."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class Action:
    type: str
    tool: str
    params: dict
    timestamp: float
    agent: str = ""


@dataclass
class Observation:
    type: str
    result: Any
    success: bool
    elapsed_ms: int
    truncated: bool = False


@dataclass
class TrajectoryStep:
    action: Action
    observation: Observation


class TrajectoryRecorder:
    """Records agent tool calls and results for export/debugging."""

    def __init__(self) -> None:
        self._steps: list[TrajectoryStep] = []
        self._session_start = time.time()

    def record(self, action: Action, observation: Observation) -> None:
        self._steps.append(TrajectoryStep(action=action, observation=observation))

    def record_tool_event(
        self,
        event: str,
        tool_name: str,
        args: dict | None,
        result: Any,
        agent: str = "",
        elapsed_ms: int = 0,
    ) -> None:
        """Convenience method matching the tool_event_callback signature."""
        if event != "end":
            return  # Only record completed calls
        action = Action(
            type="tool_call",
            tool=tool_name,
            params=args or {},
            timestamp=time.time(),
            agent=agent,
        )
        success = not (isinstance(result, str) and result.startswith("Error"))
        # Truncate large results
        result_str = str(result) if result is not None else ""
        truncated = len(result_str) > 1000
        obs = Observation(
            type="tool_result",
            result=result_str[:1000] if truncated else result_str,
            success=success,
            elapsed_ms=elapsed_ms,
            truncated=truncated,
        )
        self._steps.append(TrajectoryStep(action=action, observation=obs))

    def export_json(self, path: str) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "session_start": self._session_start,
            "steps": [
                {
                    "action": asdict(s.action),
                    "observation": {
                        **asdict(s.observation),
                        "result": str(s.observation.result),
                    },
                }
                for s in self._steps
            ],
        }
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def export_jsonl(self, path: str) -> None:
        """One JSON object per line -- fine-tuning format."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for s in self._steps:
            lines.append(json.dumps({
                "action": asdict(s.action),
                "observation": {
                    **asdict(s.observation),
                    "result": str(s.observation.result),
                },
            }))
        out.write_text("\n".join(lines), encoding="utf-8")

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        total_ms = 0
        errors = 0
        for s in self._steps:
            counts[s.action.tool] = counts.get(s.action.tool, 0) + 1
            total_ms += s.observation.elapsed_ms
            if not s.observation.success:
                errors += 1
        return {
            "total_steps": len(self._steps),
            "tool_counts": counts,
            "total_elapsed_ms": total_ms,
            "error_count": errors,
        }

    @property
    def steps(self) -> list[TrajectoryStep]:
        return list(self._steps)
