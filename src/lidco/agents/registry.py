"""Agent registry for managing available agents."""

from __future__ import annotations

from lidco.agents.base import BaseAgent


class AgentRegistry:
    """Registry for discovering and managing agents."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent."""
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent | None:
        """Get an agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[BaseAgent]:
        """List all registered agents."""
        return list(self._agents.values())

    def list_names(self) -> list[str]:
        """List all agent names."""
        return list(self._agents.keys())
