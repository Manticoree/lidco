"""MCP server lifecycle manager — Task 253.

MCPManager holds all active MCPClient instances and handles reconnection.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from lidco.mcp.client import MCPClient, MCPClientError, MCPToolSchema
from lidco.mcp.config import MCPConfig, MCPServerEntry

logger = logging.getLogger(__name__)

_BACKOFF_BASE = 1.0   # seconds
_BACKOFF_MAX = 30.0   # seconds
_MAX_RECONNECT_ATTEMPTS = 5


@dataclass
class ServerStatus:
    """Runtime status for a managed server."""
    name: str
    transport: str
    connected: bool = False
    tool_count: int = 0
    last_error: str = ""
    connected_at: datetime | None = None
    reconnect_attempts: int = 0


class MCPManager:
    """Manages lifecycle of all MCP server connections.

    Typical usage::

        manager = MCPManager()
        await manager.start_all(config)
        tools = manager.all_tool_schemas()
        # ... session runs ...
        await manager.stop_all()
    """

    def __init__(self) -> None:
        self._clients: dict[str, MCPClient] = {}
        self._statuses: dict[str, ServerStatus] = {}
        self._tool_schemas: dict[str, list[MCPToolSchema]] = {}  # server → tools

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_all(self, config: MCPConfig) -> None:
        """Connect all enabled stdio servers. HTTP servers connected separately."""
        tasks = [
            self._connect_server(entry)
            for entry in config.enabled_servers()
            if entry.is_stdio
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def start_server(self, entry: MCPServerEntry) -> bool:
        """Connect a single server entry. Returns True on success."""
        return await self._connect_server(entry)

    async def stop_all(self) -> None:
        """Disconnect all active clients."""
        tasks = [client.disconnect() for client in self._clients.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._clients.clear()
        self._statuses.clear()
        self._tool_schemas.clear()

    async def stop_server(self, name: str) -> None:
        """Disconnect a single server."""
        client = self._clients.pop(name, None)
        if client:
            await client.disconnect()
        self._statuses.pop(name, None)
        self._tool_schemas.pop(name, None)

    async def reconnect(self, name: str, config_entry: MCPServerEntry) -> bool:
        """Force-reconnect a server with exponential backoff."""
        await self.stop_server(name)
        status = self._statuses.get(name) or ServerStatus(name=name, transport=config_entry.transport)
        for attempt in range(1, _MAX_RECONNECT_ATTEMPTS + 1):
            status.reconnect_attempts += 1
            backoff = min(_BACKOFF_BASE * (2 ** (attempt - 1)), _BACKOFF_MAX)
            logger.info("MCP reconnect '%s' attempt %d/%d (backoff %.1fs)",
                        name, attempt, _MAX_RECONNECT_ATTEMPTS, backoff)
            await asyncio.sleep(backoff)
            success = await self._connect_server(config_entry)
            if success:
                status.reconnect_attempts = 0
                return True
        logger.warning("MCP server '%s' failed to reconnect after %d attempts", name, _MAX_RECONNECT_ATTEMPTS)
        return False

    def get_client(self, name: str) -> MCPClient | None:
        return self._clients.get(name)

    def all_tool_schemas(self) -> dict[str, list[MCPToolSchema]]:
        """Return all tool schemas keyed by server name."""
        return dict(self._tool_schemas)

    def get_status(self, name: str | None = None) -> dict[str, ServerStatus]:
        if name:
            s = self._statuses.get(name)
            return {name: s} if s else {}
        return dict(self._statuses)

    def server_names(self) -> list[str]:
        return list(self._clients.keys())

    def is_connected(self, name: str) -> bool:
        client = self._clients.get(name)
        return client is not None and client.is_connected

    def update_config(self, old_config: MCPConfig, new_config: MCPConfig) -> tuple[list[str], list[str]]:
        """Diff configs. Returns (removed_names, added_entries).

        Used by hot-reload. Caller is responsible for stop/start.
        """
        old_names = {e.name for e in old_config.servers}
        new_names = {e.name for e in new_config.servers}
        removed = list(old_names - new_names)
        added = [e for e in new_config.servers if e.name not in old_names]
        return removed, [e.name for e in added]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _connect_server(self, entry: MCPServerEntry) -> bool:
        status = ServerStatus(name=entry.name, transport=entry.transport)
        self._statuses[entry.name] = status

        if entry.is_http:
            # HTTP/SSE handled by http_client — placeholder for now
            status.last_error = "HTTP/SSE transport not yet connected (use MCPHttpClient)"
            logger.debug("Skipping HTTP MCP server '%s' — use http_client", entry.name)
            return False

        if not entry.command:
            status.last_error = "No command specified for stdio transport"
            logger.warning("MCP server '%s' has no command", entry.name)
            return False

        client = MCPClient(
            name=entry.name,
            command=entry.command,
            env=entry.env or {},
            tool_timeout=entry.timeout,
        )

        try:
            await client.connect()
        except MCPClientError as exc:
            status.last_error = str(exc)
            logger.warning("MCP server '%s' failed to connect: %s", entry.name, exc)
            return False

        # Fetch tools
        try:
            tools = await client.list_tools()
        except MCPClientError as exc:
            logger.warning("MCP server '%s' tools/list failed: %s", entry.name, exc)
            tools = []

        self._clients[entry.name] = client
        self._tool_schemas[entry.name] = tools
        status.connected = True
        status.tool_count = len(tools)
        status.connected_at = datetime.now()
        status.last_error = ""
        logger.info("MCP server '%s' ready with %d tool(s)", entry.name, len(tools))
        return True
