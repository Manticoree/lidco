"""Claude Code manifest parser and converter (Task 952)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lidco.marketplace.manifest import Capability, PluginManifest, TrustLevel


# ---- Permission mapping from Claude Code to LIDCO capabilities ----

_CC_PERMISSION_MAP: dict[str, Capability] = {
    "read": Capability.FILE_READ,
    "file_read": Capability.FILE_READ,
    "files:read": Capability.FILE_READ,
    "write": Capability.FILE_WRITE,
    "file_write": Capability.FILE_WRITE,
    "files:write": Capability.FILE_WRITE,
    "network": Capability.NETWORK,
    "net": Capability.NETWORK,
    "http": Capability.NETWORK,
    "execute": Capability.EXECUTE,
    "exec": Capability.EXECUTE,
    "run": Capability.EXECUTE,
    "shell": Capability.EXECUTE,
    "git": Capability.GIT,
    "database": Capability.DATABASE,
    "db": Capability.DATABASE,
    "sql": Capability.DATABASE,
}


@dataclass
class CCPluginManifest:
    """Parsed Claude Code plugin manifest."""

    name: str = ""
    version: str = ""
    description: str = ""
    author: str = ""
    permissions: list[str] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)
    user_config: dict = field(default_factory=dict)
    homepage: str = ""
    repository: str = ""


def parse_cc_manifest(data: dict[str, Any]) -> CCPluginManifest:
    """Parse a Claude Code ``manifest.json`` into *CCPluginManifest*."""
    if not isinstance(data, dict):
        raise TypeError("manifest data must be a dict")
    return CCPluginManifest(
        name=str(data.get("name", "")),
        version=str(data.get("version", "")),
        description=str(data.get("description", "")),
        author=str(data.get("author", "")),
        permissions=list(data.get("permissions", [])),
        tools=list(data.get("tools", [])),
        user_config=dict(data.get("user_config", data.get("userConfig", {}))),
        homepage=str(data.get("homepage", "")),
        repository=str(data.get("repository", "")),
    )


def _map_permissions(perms: list[str]) -> list[Capability]:
    """Map Claude Code permission strings to LIDCO capabilities (deduplicated)."""
    seen: set[Capability] = set()
    result: list[Capability] = []
    for p in perms:
        cap = _CC_PERMISSION_MAP.get(p.lower().strip())
        if cap is not None and cap not in seen:
            seen.add(cap)
            result.append(cap)
    return result


def _infer_trust_level(cc: CCPluginManifest) -> TrustLevel:
    """Infer LIDCO trust level from Claude Code manifest fields."""
    # If the manifest has a repository and homepage, treat as community
    if cc.repository and cc.homepage:
        return TrustLevel.COMMUNITY
    return TrustLevel.UNVERIFIED


def to_lidco_manifest(cc: CCPluginManifest) -> PluginManifest:
    """Convert a *CCPluginManifest* to a LIDCO *PluginManifest*."""
    return PluginManifest(
        name=cc.name,
        version=cc.version or "0.0.0",
        description=cc.description,
        author=cc.author,
        trust_level=_infer_trust_level(cc),
        capabilities=_map_permissions(cc.permissions),
        homepage=cc.homepage or cc.repository,
    )
