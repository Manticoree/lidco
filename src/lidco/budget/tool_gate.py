"""Pre-execution budget gate for tool calls."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GateDecision(str, Enum):
    """Outcome of a budget gate check."""

    ALLOW = "ALLOW"
    WARN = "WARN"
    DENY = "DENY"
    OVERRIDE = "OVERRIDE"


@dataclass(frozen=True)
class GateResult:
    """Result of a budget gate check."""

    decision: GateDecision
    tool_name: str
    estimated_tokens: int = 0
    budget_remaining: int = 0
    message: str = ""


class ToolBudgetGate:
    """Pre-execution budget gate for tool calls.

    Critical tools (e.g. Write, Edit) are always allowed even when
    the budget is exhausted — they receive an OVERRIDE decision.
    """

    def __init__(
        self,
        budget_remaining: int = 100_000,
        warn_threshold: int = 5_000,
        critical_tools: tuple[str, ...] = ("Write", "Edit"),
    ) -> None:
        self._budget_remaining = budget_remaining
        self._warn_threshold = warn_threshold
        self._critical_tools: set[str] = set(critical_tools)
        self._denied_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, tool_name: str, estimated_tokens: int) -> GateResult:
        """Evaluate whether *tool_name* should be allowed to run."""
        if self.is_critical(tool_name):
            if estimated_tokens > self._budget_remaining:
                return GateResult(
                    decision=GateDecision.OVERRIDE,
                    tool_name=tool_name,
                    estimated_tokens=estimated_tokens,
                    budget_remaining=self._budget_remaining,
                    message=f"Critical tool '{tool_name}' overrides budget limit",
                )
            return GateResult(
                decision=GateDecision.ALLOW,
                tool_name=tool_name,
                estimated_tokens=estimated_tokens,
                budget_remaining=self._budget_remaining,
                message="OK",
            )

        if estimated_tokens > self._budget_remaining:
            self._denied_count += 1
            return GateResult(
                decision=GateDecision.DENY,
                tool_name=tool_name,
                estimated_tokens=estimated_tokens,
                budget_remaining=self._budget_remaining,
                message=(
                    f"Denied: {tool_name} needs ~{estimated_tokens} tokens "
                    f"but only {self._budget_remaining} remain"
                ),
            )

        if self._budget_remaining < self._warn_threshold:
            return GateResult(
                decision=GateDecision.WARN,
                tool_name=tool_name,
                estimated_tokens=estimated_tokens,
                budget_remaining=self._budget_remaining,
                message=(
                    f"Warning: budget low ({self._budget_remaining} tokens remaining)"
                ),
            )

        return GateResult(
            decision=GateDecision.ALLOW,
            tool_name=tool_name,
            estimated_tokens=estimated_tokens,
            budget_remaining=self._budget_remaining,
            message="OK",
        )

    def update_budget(self, remaining: int) -> None:
        """Set the current remaining budget."""
        self._budget_remaining = remaining

    def is_critical(self, tool_name: str) -> bool:
        """Return whether *tool_name* is in the critical set."""
        return tool_name in self._critical_tools

    def add_critical(self, tool_name: str) -> None:
        """Add *tool_name* to the critical-tools set."""
        self._critical_tools = self._critical_tools | {tool_name}

    def get_denied_count(self) -> int:
        """Return the number of DENY decisions issued so far."""
        return self._denied_count

    def summary(self) -> str:
        """Human-readable summary of gate state."""
        critical = ", ".join(sorted(self._critical_tools)) or "(none)"
        return (
            f"ToolBudgetGate: budget={self._budget_remaining}, "
            f"warn_threshold={self._warn_threshold}, "
            f"denied={self._denied_count}, critical=[{critical}]"
        )
