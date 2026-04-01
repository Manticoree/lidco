"""Initialize budget for a new session based on model and config."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionBudgetInit:
    """Immutable budget initialization result."""

    model: str = ""
    context_limit: int = 128000
    max_output: int = 4096
    system_prompt_reserve: int = 3000
    tool_reserve: int = 5000
    available_for_conversation: int = 0


class SessionInitializer:
    """Compute initial token budget for a session."""

    def __init__(self, default_limit: int = 128000) -> None:
        self._default = default_limit

    def initialize(
        self,
        model: str = "",
        context_limit: int = 0,
        system_prompt_tokens: int = 0,
    ) -> SessionBudgetInit:
        """Build a :class:`SessionBudgetInit` for the given parameters."""
        limit = context_limit if context_limit > 0 else self._default
        sys_reserve = system_prompt_tokens if system_prompt_tokens > 0 else 3000
        tool_reserve = 5000
        available = max(0, limit - sys_reserve - tool_reserve)
        return SessionBudgetInit(
            model=model,
            context_limit=limit,
            max_output=4096,
            system_prompt_reserve=sys_reserve,
            tool_reserve=tool_reserve,
            available_for_conversation=available,
        )

    def estimate_system_tokens(self, system_prompt: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return len(system_prompt) // 4

    def recommend_reserves(self, context_limit: int) -> dict[str, int]:
        """Return recommended reserves for *context_limit*."""
        return {
            "system": min(5000, int(context_limit * 0.05)),
            "tools": min(10000, int(context_limit * 0.1)),
            "buffer": min(5000, int(context_limit * 0.05)),
        }

    def summary(self, init: SessionBudgetInit) -> str:
        """Human-readable summary of the budget initialization."""
        lines = [
            f"Model: {init.model or '(default)'}",
            f"Context limit: {init.context_limit:,}",
            f"System prompt reserve: {init.system_prompt_reserve:,}",
            f"Tool reserve: {init.tool_reserve:,}",
            f"Available for conversation: {init.available_for_conversation:,}",
        ]
        return "\n".join(lines)
