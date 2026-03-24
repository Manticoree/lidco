"""Load ContextProvider instances from YAML config."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import ContextProvider
from .command_provider import CommandContextProvider
from .file_provider import FileContextProvider
from .url_provider import URLContextProvider


class ContextProviderRegistry:
    """Registry of context providers, collected by priority."""

    def __init__(self) -> None:
        self._providers: list[ContextProvider] = []

    def register(self, provider: ContextProvider) -> None:
        self._providers.append(provider)

    def unregister(self, name: str) -> bool:
        before = len(self._providers)
        self._providers = [p for p in self._providers if p.name != name]
        return len(self._providers) < before

    def get(self, name: str) -> ContextProvider | None:
        return next((p for p in self._providers if p.name == name), None)

    @property
    def providers(self) -> list[ContextProvider]:
        return list(self._providers)

    async def collect(self, budget_tokens: int = 4000) -> str:
        """Fetch all providers sorted by priority (desc) within token budget."""
        sorted_providers = sorted(self._providers, key=lambda p: p.priority, reverse=True)
        parts = []
        remaining = budget_tokens
        for provider in sorted_providers:
            if remaining <= 0:
                break
            content = await provider.fetch()
            # Rough token estimate: 4 chars per token
            estimated_tokens = len(content) // 4
            if estimated_tokens > provider.max_tokens:
                content = content[: provider.max_tokens * 4]
                estimated_tokens = provider.max_tokens
            if estimated_tokens <= remaining:
                parts.append(f"## {provider.name}\n{content}")
                remaining -= estimated_tokens
        return "\n\n".join(parts)

    def reload(self, config_path: Path) -> None:
        """Reload providers from YAML config file."""
        self._providers.clear()
        if not config_path.exists():
            return
        try:
            import yaml
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return
        for entry in data.get("providers", []):
            provider = _build_provider(entry)
            if provider:
                self._providers.append(provider)


def _build_provider(entry: dict[str, Any]) -> ContextProvider | None:
    ptype = entry.get("type", "")
    name = entry.get("name", ptype)
    priority = int(entry.get("priority", 50))
    max_tokens = int(entry.get("max_tokens", 2000))

    if ptype == "file":
        return FileContextProvider(name=name, pattern=entry.get("pattern", "**/*"), priority=priority, max_tokens=max_tokens)
    elif ptype == "url":
        return URLContextProvider(name=name, url=entry.get("url", ""), cache_ttl=int(entry.get("cache_ttl", 300)), priority=priority, max_tokens=max_tokens)
    elif ptype == "command":
        return CommandContextProvider(name=name, command=entry.get("command", "echo"), priority=priority, max_tokens=max_tokens)
    return None
