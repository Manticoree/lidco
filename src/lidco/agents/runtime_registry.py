"""RuntimeAgentRegistry — persist and hot-reload synthesized agents."""
from __future__ import annotations

from pathlib import Path

from .factory import AgentConfig


class RuntimeAgentRegistry:
    """File-backed registry of synthesized agent configs."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._project_dir = project_dir or Path.cwd()
        self._agents_dir = self._project_dir / ".lidco" / "agents"
        self._cache: dict[str, AgentConfig] = {}

    def register(self, config: AgentConfig) -> None:
        """Register an agent config in memory and on disk."""
        self._cache[config.name] = config
        self._write_yaml(config)

    def get(self, name: str) -> AgentConfig | None:
        """Get agent by name, checking disk for hot-reloaded entries."""
        if name in self._cache:
            return self._cache[name]
        # Try loading from disk
        config = self._load_from_disk(name)
        if config:
            self._cache[name] = config
        return config

    def list(self) -> list[AgentConfig]:
        """List all registered agents (memory + disk)."""
        self._reload_from_disk()
        return list(self._cache.values())

    def unregister(self, name: str) -> bool:
        if name in self._cache:
            del self._cache[name]
        path = self._agents_dir / f"{name}.yaml"
        if path.exists():
            path.unlink()
            return True
        return False

    def _reload_from_disk(self) -> None:
        if not self._agents_dir.exists():
            return
        for yaml_path in self._agents_dir.glob("*.yaml"):
            name = yaml_path.stem
            if name not in self._cache:
                config = self._load_from_disk(name)
                if config:
                    self._cache[name] = config

    def _load_from_disk(self, name: str) -> AgentConfig | None:
        yaml_path = self._agents_dir / f"{name}.yaml"
        if not yaml_path.exists():
            return None
        try:
            try:
                import yaml
                data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            except ImportError:
                data = _parse_simple_yaml(yaml_path.read_text(encoding="utf-8"))
            return AgentConfig(
                name=data.get("name", name),
                description=data.get("description", ""),
                system_prompt=data.get("system_prompt", ""),
                tools=data.get("tools") or [],
                model=data.get("model", "openai/glm-4.7"),
                max_iterations=int(data.get("max_iterations", 50)),
            )
        except Exception:
            return None

    def _write_yaml(self, config: AgentConfig) -> None:
        self._agents_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = self._agents_dir / f"{config.name}.yaml"
        content = (
            f"name: {config.name}\n"
            f"description: {config.description}\n"
            f"model: {config.model}\n"
            f"max_iterations: {config.max_iterations}\n"
            f"tools:\n" + "".join(f"  - {t}\n" for t in config.tools) +
            f"system_prompt: |\n  {config.system_prompt}\n"
        )
        yaml_path.write_text(content, encoding="utf-8")


def _parse_simple_yaml(text: str) -> dict:
    """Minimal YAML key:value parser for when PyYAML unavailable."""
    result: dict = {}
    for line in text.splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result
