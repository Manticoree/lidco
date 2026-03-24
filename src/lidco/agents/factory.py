"""AgentFactory — synthesize a new agent spec from a NL description at runtime."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class AgentConfig:
    name: str
    description: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    model: str = "openai/glm-4.7"
    max_iterations: int = 50


_KNOWN_TOOLS = frozenset({
    "file_read", "file_write", "file_edit", "bash", "glob", "grep",
    "git_status", "git_diff", "git_log", "web_search", "error_report",
})

_DEFAULT_TOOLS = ["file_read", "file_write", "file_edit", "bash", "glob", "grep"]


class AgentFactory:
    """Synthesize a complete agent spec from a natural language description."""

    def __init__(
        self,
        project_dir: Path | None = None,
        llm_fn: Callable[[str], str] | None = None,
    ) -> None:
        self._project_dir = project_dir or Path.cwd()
        self._llm_fn = llm_fn

    def synthesize(self, description: str) -> AgentConfig:
        """Generate an AgentConfig from a NL description."""
        name = _slugify(description)

        if self._llm_fn:
            try:
                raw = self._llm_fn(_build_synthesis_prompt(description))
                config = _parse_llm_response(raw, name, description)
            except Exception:
                config = _default_config(name, description)
        else:
            config = _default_config(name, description)

        # Validate tool names
        config.tools = [t for t in config.tools if t in _KNOWN_TOOLS] or _DEFAULT_TOOLS

        # Persist to .lidco/agents/<name>.yaml
        self._write_yaml(config)
        return config

    def _write_yaml(self, config: AgentConfig) -> None:
        agents_dir = self._project_dir / ".lidco" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = agents_dir / f"{config.name}.yaml"
        content = (
            f"name: {config.name}\n"
            f"description: {config.description}\n"
            f"model: {config.model}\n"
            f"max_iterations: {config.max_iterations}\n"
            f"tools:\n" + "".join(f"  - {t}\n" for t in config.tools) +
            f"system_prompt: |\n  {config.system_prompt.replace(chr(10), chr(10) + '  ')}\n"
        )
        yaml_path.write_text(content, encoding="utf-8")


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text[:40] or "agent"


def _build_synthesis_prompt(description: str) -> str:
    return (
        f"Synthesize an AI agent spec for: {description}\n\n"
        "Return JSON with keys: name (slug), system_prompt, tools (list), model, max_iterations"
    )


def _parse_llm_response(raw: str, fallback_name: str, description: str) -> AgentConfig:
    import json
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return _default_config(fallback_name, description)
    data = json.loads(raw[start:end])
    return AgentConfig(
        name=_slugify(data.get("name", fallback_name)),
        description=description,
        system_prompt=data.get("system_prompt", f"You are a helpful agent for: {description}"),
        tools=data.get("tools", _DEFAULT_TOOLS),
        model=data.get("model", "openai/glm-4.7"),
        max_iterations=int(data.get("max_iterations", 50)),
    )


def _default_config(name: str, description: str) -> AgentConfig:
    return AgentConfig(
        name=name,
        description=description,
        system_prompt=f"You are a specialized agent for: {description}",
        tools=list(_DEFAULT_TOOLS),
        model="openai/glm-4.7",
        max_iterations=50,
    )
