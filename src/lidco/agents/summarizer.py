"""Agent Summarizer — record agent actions and produce structured summaries."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentAction:
    """A single action performed by an agent."""

    action_type: str
    target: str
    timestamp: str


@dataclass(frozen=True)
class AgentSummary:
    """Summary of an agent's work session."""

    agent_name: str
    actions: tuple[AgentAction, ...]
    files_modified: tuple[str, ...]
    duration_ms: int
    cost: float
    key_decisions: tuple[str, ...]


class AgentSummarizer:
    """Records agent actions and produces a summary.

    Immutable-style: :meth:`record_action` returns a new summarizer.
    """

    def __init__(
        self,
        agent_name: str = "agent",
        actions: tuple[AgentAction, ...] = (),
        start_time: float | None = None,
    ) -> None:
        self._agent_name = agent_name
        self._actions = actions
        self._start_time = start_time if start_time is not None else time.monotonic()

    def record_action(self, action: AgentAction) -> AgentSummarizer:
        """Return a new summarizer with *action* appended."""
        return AgentSummarizer(
            agent_name=self._agent_name,
            actions=(*self._actions, action),
            start_time=self._start_time,
        )

    def summarize(self) -> AgentSummary:
        """Produce a summary from recorded actions."""
        files = tuple(
            sorted(
                {
                    a.target
                    for a in self._actions
                    if a.action_type in ("edit", "create", "delete", "write")
                }
            )
        )
        decisions = tuple(
            a.target
            for a in self._actions
            if a.action_type in ("decide", "approve", "reject")
        )
        elapsed_ms = int((time.monotonic() - self._start_time) * 1000)
        return AgentSummary(
            agent_name=self._agent_name,
            actions=self._actions,
            files_modified=files,
            duration_ms=elapsed_ms,
            cost=0.0,
            key_decisions=decisions,
        )

    def format_markdown(self) -> str:
        """Format the summary as markdown."""
        summary = self.summarize()
        lines = [
            f"# Agent Summary: {summary.agent_name}",
            "",
            f"- **Actions**: {len(summary.actions)}",
            f"- **Files modified**: {len(summary.files_modified)}",
            f"- **Duration**: {summary.duration_ms}ms",
            f"- **Cost**: ${summary.cost:.6f}",
        ]
        if summary.files_modified:
            lines.append("")
            lines.append("## Files Modified")
            for f in summary.files_modified:
                lines.append(f"- `{f}`")
        if summary.key_decisions:
            lines.append("")
            lines.append("## Key Decisions")
            for d in summary.key_decisions:
                lines.append(f"- {d}")
        return "\n".join(lines)


__all__ = ["AgentAction", "AgentSummary", "AgentSummarizer"]
