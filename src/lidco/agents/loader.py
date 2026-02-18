"""YAML-based agent loader for custom agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry


class YAMLAgent(BaseAgent):
    """An agent loaded from a YAML configuration file."""

    def get_system_prompt(self) -> str:
        return self._config.system_prompt


def load_agent_from_yaml(
    path: Path,
    llm: BaseLLMProvider,
    tool_registry: ToolRegistry,
) -> BaseAgent:
    """Load an agent from a YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)

    model_config = data.get("model", {})

    config = AgentConfig(
        name=data["name"],
        description=data.get("description", ""),
        system_prompt=data.get("system_prompt", "You are a helpful assistant."),
        model=model_config.get("preferred"),
        temperature=model_config.get("temperature", 0.1),
        tools=data.get("tools", []),
        fallback_model=model_config.get("fallback"),
        context_window=model_config.get("context_window", 128_000),
    )

    return YAMLAgent(config=config, llm=llm, tool_registry=tool_registry)


def discover_yaml_agents(
    llm: BaseLLMProvider,
    tool_registry: ToolRegistry,
    search_dirs: list[Path] | None = None,
) -> list[BaseAgent]:
    """Discover and load all YAML agents from standard directories."""
    if search_dirs is None:
        search_dirs = [
            Path.home() / ".lidco" / "agents",
            Path.cwd() / ".lidco" / "agents",
        ]

    agents: list[BaseAgent] = []

    for directory in search_dirs:
        if not directory.exists():
            continue
        for yaml_file in sorted(directory.glob("*.yaml")):
            try:
                agent = load_agent_from_yaml(yaml_file, llm, tool_registry)
                agents.append(agent)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "Failed to load agent from %s: %s", yaml_file, e
                )

    return agents
