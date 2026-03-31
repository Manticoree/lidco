"""Claude Code MCP config adapter (Task 953)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CCMCPServer:
    """Parsed Claude Code MCP server entry."""

    name: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"
    url: str | None = None


def parse_cc_mcp_config(settings: dict[str, Any]) -> list[CCMCPServer]:
    """Parse the ``mcpServers`` section from ``.claude/settings.json``.

    Returns a list of *CCMCPServer* entries.
    """
    if not isinstance(settings, dict):
        raise TypeError("settings must be a dict")

    servers_raw = settings.get("mcpServers", {})
    if not isinstance(servers_raw, dict):
        return []

    servers: list[CCMCPServer] = []
    for name, cfg in servers_raw.items():
        if not isinstance(cfg, dict):
            continue
        transport = str(cfg.get("transport", "")).lower()
        # Infer transport from available fields if not explicit
        if not transport:
            if cfg.get("url"):
                transport = "sse"
            else:
                transport = "stdio"

        servers.append(CCMCPServer(
            name=str(name),
            command=str(cfg.get("command", "")),
            args=list(cfg.get("args", [])),
            env={str(k): str(v) for k, v in dict(cfg.get("env", {})).items()},
            transport=transport,
            url=str(cfg["url"]) if cfg.get("url") else None,
        ))
    return servers


def to_lidco_mcp_config(servers: list[CCMCPServer]) -> list[dict[str, Any]]:
    """Convert a list of *CCMCPServer* to LIDCO MCP config dicts."""
    result: list[dict[str, Any]] = []
    for srv in servers:
        entry: dict[str, Any] = {
            "name": srv.name,
            "transport": srv.transport,
        }
        if srv.transport == "stdio":
            entry["command"] = srv.command
            if srv.args:
                entry["args"] = list(srv.args)
            if srv.env:
                entry["env"] = dict(srv.env)
        elif srv.transport in ("sse", "streamable-http"):
            if srv.url:
                entry["url"] = srv.url
            if srv.env:
                entry["env"] = dict(srv.env)
        else:
            # Fallback: include all fields
            entry["command"] = srv.command
            if srv.args:
                entry["args"] = list(srv.args)
            if srv.url:
                entry["url"] = srv.url
            if srv.env:
                entry["env"] = dict(srv.env)
        result.append(entry)
    return result
