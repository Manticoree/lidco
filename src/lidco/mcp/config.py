"""MCP server configuration — Task 257.

Config hierarchy (project wins over user):
  ~/.lidco/mcp.json         — user-level defaults
  .lidco/mcp.json           — project-level overrides
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_USER_MCP_PATH = Path.home() / ".lidco" / "mcp.json"


class MCPServerEntry(BaseModel):
    """Configuration for a single MCP server."""

    name: str
    # stdio transport: command + args list
    command: list[str] = Field(default_factory=list)
    # HTTP/SSE transport: full URL
    url: str = ""
    transport: Literal["stdio", "sse"] = "stdio"
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    # Auth config: {"type": "bearer", "token": "..."} for manual tokens
    auth: dict[str, Any] | None = None
    # Tool call timeout in seconds (default 30)
    timeout: float = 30.0

    @property
    def is_stdio(self) -> bool:
        return self.transport == "stdio"

    @property
    def is_http(self) -> bool:
        return self.transport == "sse"


class MCPConfig(BaseModel):
    """Root MCP configuration."""

    servers: list[MCPServerEntry] = Field(default_factory=list)

    def get_server(self, name: str) -> MCPServerEntry | None:
        return next((s for s in self.servers if s.name == name), None)

    def enabled_servers(self) -> list[MCPServerEntry]:
        return [s for s in self.servers if s.enabled]


def _load_json(path: Path) -> dict[str, Any]:
    """Load JSON from path, return {} on error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return {}


def load_mcp_config(project_dir: Path) -> MCPConfig:
    """Merge user + project mcp.json into MCPConfig (project wins).

    Server names are unique keys — a project entry overrides the user entry
    with the same name; unknown project entries are appended.
    """
    user_data = _load_json(_USER_MCP_PATH)
    project_data = _load_json(project_dir / ".lidco" / "mcp.json")

    # Build server map: start with user, overlay project
    servers: dict[str, dict[str, Any]] = {}
    for entry in user_data.get("servers", []):
        if isinstance(entry, dict) and "name" in entry:
            servers[entry["name"]] = entry
    for entry in project_data.get("servers", []):
        if isinstance(entry, dict) and "name" in entry:
            servers[entry["name"]] = entry

    validated: list[MCPServerEntry] = []
    for raw in servers.values():
        try:
            validated.append(MCPServerEntry.model_validate(raw))
        except Exception as exc:
            logger.warning("Skipping invalid MCP server entry %s: %s", raw.get("name"), exc)

    return MCPConfig(servers=validated)
