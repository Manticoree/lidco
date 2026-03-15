"""YAML-based agent loader for custom agents.

Supports two file formats:
  * Pure YAML/YML: ``agent.yaml`` — the entire file is a YAML mapping.
  * Markdown with frontmatter: ``agent.md`` — YAML between ``---`` delimiters,
    body below becomes the system_prompt (overrides frontmatter's system_prompt
    when body is non-empty).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def _parse_md_agent(text: str) -> dict[str, Any]:
    """Parse a Markdown+YAML-frontmatter agent file into a raw data dict.

    The YAML block between the first ``---`` delimiters provides config.
    The Markdown body below the closing ``---`` becomes ``system_prompt``
    when non-empty (overrides any ``system_prompt`` in the frontmatter).
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("No YAML frontmatter found (expected --- ... --- block)")
    data: dict[str, Any] = yaml.safe_load(m.group(1)) or {}
    body = m.group(2).strip()
    if body:
        data["system_prompt"] = body
    return data


class YAMLAgent(BaseAgent):
    """An agent loaded from a YAML configuration file."""

    def get_system_prompt(self) -> str:
        return self._config.system_prompt


def _load_raw_data(path: Path) -> dict[str, Any]:
    """Load raw data dict from a .yaml, .yml, or .md agent file."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        return _parse_md_agent(text)
    return yaml.safe_load(text) or {}


def load_agent_from_yaml(
    path: Path,
    llm: BaseLLMProvider,
    tool_registry: ToolRegistry,
) -> BaseAgent:
    """Load an agent from a YAML or Markdown-frontmatter file.

    Required fields: ``name`` (str), ``system_prompt`` (str).
    Optional fields: ``description``, ``model``, ``temperature``, ``tools``,
    ``routing_keywords``, ``disallowed_tools``, ``permission_mode``,
    ``memory``, ``isolation``, ``hooks``, ``max_turns``.

    Backward-compat: if ``model`` is a dict (old nested format), ``model.preferred``
    and ``model.temperature`` are extracted with a deprecation warning.

    Raises:
        ValueError: if required fields are missing or empty.
    """
    data = _load_raw_data(path)

    # Validate required fields
    missing = [f for f in ("name", "system_prompt") if not data.get(f)]
    if missing:
        raise ValueError(
            f"YAML agent '{path.name}' missing required field(s): {', '.join(missing)}"
        )

    # Handle old nested model format (backward-compat)
    model_val = data.get("model")
    if isinstance(model_val, dict):
        logger.warning(
            "Agent '%s' uses deprecated nested 'model:' format in %s. "
            "Use flat 'model: <name>' instead.",
            data["name"], path,
        )
        temperature = model_val.get("temperature", 0.1)
        fallback_model = model_val.get("fallback")
        context_window = model_val.get("context_window", 128_000)
        model_str: str | None = model_val.get("preferred")
    else:
        temperature = data.get("temperature", 0.1)
        fallback_model = None
        context_window = 128_000
        model_str = model_val  # string or None

    tools: list[str] = data.get("tools", [])
    disallowed: list[str] = data.get("disallowed_tools", [])

    # max_turns maps to max_iterations
    max_turns = data.get("max_turns")
    max_iterations = int(max_turns) if max_turns is not None else 200

    config = AgentConfig(
        name=data["name"],
        description=data.get("description", ""),
        system_prompt=data["system_prompt"],
        model=model_str,
        temperature=temperature,
        tools=tools,
        max_iterations=max_iterations,
        fallback_model=fallback_model,
        context_window=context_window,
        routing_keywords=data.get("routing_keywords", []),
        disallowed_tools=disallowed,
        permission_mode=data.get("permission_mode"),
        memory=data.get("memory", "project"),
        isolation=data.get("isolation", "none"),
        hooks=data.get("hooks") or {},
    )

    # Warn about unknown tool names — agent is still created successfully
    for tool_name in tools:
        if tool_registry.get(tool_name) is None:
            logger.warning(
                "Agent '%s' references unknown tool '%s' (from %s) — "
                "it will be ignored at runtime.",
                config.name, tool_name, path,
            )

    return YAMLAgent(config=config, llm=llm, tool_registry=tool_registry)


def discover_yaml_agents(
    llm: BaseLLMProvider,
    tool_registry: ToolRegistry,
    search_dirs: list[Path] | None = None,
    project_dir: Path | None = None,
) -> list[BaseAgent]:
    """Discover and load all YAML agents from standard directories.

    Searches ``~/.lidco/agents/`` and ``<project_dir>/.lidco/agents/``
    by default (falls back to cwd when ``project_dir`` is not supplied).
    Both ``.yaml`` and ``.yml`` extensions are supported.
    Invalid files are skipped with a WARNING.
    """
    if search_dirs is None:
        project_agents_dir = (project_dir or Path.cwd()) / ".lidco" / "agents"
        search_dirs = [
            Path.home() / ".lidco" / "agents",
            project_agents_dir,
        ]

    agents: list[BaseAgent] = []

    for directory in search_dirs:
        if not directory.exists():
            continue
        yaml_files = sorted(
            list(directory.glob("*.yaml"))
            + list(directory.glob("*.yml"))
            + list(directory.glob("*.md"))
        )
        for yaml_file in yaml_files:
            try:
                agent = load_agent_from_yaml(yaml_file, llm, tool_registry)
                agents.append(agent)
            except Exception as e:
                logger.warning("Failed to load agent from %s: %s", yaml_file, e)

    return agents
