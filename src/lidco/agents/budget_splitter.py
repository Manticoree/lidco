"""Split token/cost budget across subagents."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SplitMode(str, Enum):
    """How to split budget among agents."""

    EQUAL = "equal"
    PROPORTIONAL = "proportional"
    PRIORITY = "priority"


@dataclass(frozen=True)
class BudgetAllocation:
    """Budget allocated to a single agent."""

    agent_name: str
    tokens: int = 0
    cost_limit: float = 0.0
    priority: int = 1


class BudgetSplitter:
    """Split a total token/cost budget across subagents."""

    def __init__(self, total_tokens: int, total_cost: float = 0.0) -> None:
        self._total_tokens = total_tokens
        self._total_cost = total_cost

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def total_cost(self) -> float:
        return self._total_cost

    def split(
        self,
        agents: list[str],
        mode: SplitMode = SplitMode.EQUAL,
        priorities: dict[str, int] | None = None,
    ) -> list[BudgetAllocation]:
        """Split budget among agents according to mode."""
        if not agents:
            return []

        prio_map = priorities or {}
        count = len(agents)

        if mode == SplitMode.EQUAL:
            per_tokens = self._total_tokens // count
            per_cost = self._total_cost / count if count else 0.0
            return [
                BudgetAllocation(
                    agent_name=a,
                    tokens=per_tokens,
                    cost_limit=round(per_cost, 6),
                    priority=prio_map.get(a, 1),
                )
                for a in agents
            ]

        if mode == SplitMode.PROPORTIONAL:
            weights = {a: prio_map.get(a, 1) for a in agents}
            total_weight = sum(weights.values())
            return [
                BudgetAllocation(
                    agent_name=a,
                    tokens=int(self._total_tokens * weights[a] / total_weight),
                    cost_limit=round(
                        self._total_cost * weights[a] / total_weight, 6
                    ),
                    priority=weights[a],
                )
                for a in agents
            ]

        # PRIORITY: highest priority gets 50%, rest split equally
        if not prio_map:
            prio_map = {a: 1 for a in agents}
        max_prio = max(prio_map.get(a, 1) for a in agents)
        top_agents = [a for a in agents if prio_map.get(a, 1) == max_prio]
        rest_agents = [a for a in agents if prio_map.get(a, 1) != max_prio]

        top_tokens = self._total_tokens // 2
        rest_tokens = self._total_tokens - top_tokens
        top_cost = self._total_cost / 2
        rest_cost = self._total_cost - top_cost

        allocations: list[BudgetAllocation] = []
        per_top = top_tokens // len(top_agents) if top_agents else 0
        per_top_cost = top_cost / len(top_agents) if top_agents else 0.0
        for a in top_agents:
            allocations = [
                *allocations,
                BudgetAllocation(
                    agent_name=a,
                    tokens=per_top,
                    cost_limit=round(per_top_cost, 6),
                    priority=max_prio,
                ),
            ]
        if rest_agents:
            per_rest = rest_tokens // len(rest_agents)
            per_rest_cost = rest_cost / len(rest_agents)
            for a in rest_agents:
                allocations = [
                    *allocations,
                    BudgetAllocation(
                        agent_name=a,
                        tokens=per_rest,
                        cost_limit=round(per_rest_cost, 6),
                        priority=prio_map.get(a, 1),
                    ),
                ]
        return allocations

    def rebalance(
        self,
        allocations: list[BudgetAllocation],
        completed: list[str],
    ) -> list[BudgetAllocation]:
        """Redistribute completed agents' unused budget to remaining."""
        completed_set = set(completed)
        freed_tokens = sum(a.tokens for a in allocations if a.agent_name in completed_set)
        freed_cost = sum(a.cost_limit for a in allocations if a.agent_name in completed_set)
        remaining = [a for a in allocations if a.agent_name not in completed_set]
        if not remaining:
            return []
        extra_tokens = freed_tokens // len(remaining)
        extra_cost = freed_cost / len(remaining)
        return [
            BudgetAllocation(
                agent_name=a.agent_name,
                tokens=a.tokens + extra_tokens,
                cost_limit=round(a.cost_limit + extra_cost, 6),
                priority=a.priority,
            )
            for a in remaining
        ]

    def check_budget(
        self,
        agent_name: str,
        used_tokens: int,
        allocations: list[BudgetAllocation],
    ) -> bool:
        """Return True if agent is within its token budget."""
        for a in allocations:
            if a.agent_name == agent_name:
                return used_tokens <= a.tokens
        return False

    def summary(self, allocations: list[BudgetAllocation]) -> str:
        """Human-readable summary."""
        lines = [f"Budget: {self._total_tokens} tokens, ${self._total_cost:.2f}"]
        for a in allocations:
            lines = [
                *lines,
                f"  {a.agent_name}: {a.tokens} tokens, ${a.cost_limit:.4f} (p={a.priority})",
            ]
        return "\n".join(lines)
