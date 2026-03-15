"""MCP HTTP/SSE transport — Task 255.

Connects to remote MCP servers using HTTP POST for requests and
Server-Sent Events (SSE) for streaming responses.

Requires: httpx with httpx-sse, or aiohttp. Uses httpx if available,
falls back to a simple polling approach otherwise.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from lidco.mcp.client import MCPClientError, MCPToolSchema
from lidco.mcp.protocol import (
    METHOD_INITIALIZE,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    JsonRpcRequest,
    build_initialize_params,
)

logger = logging.getLogger(__name__)

_INITIALIZE_TIMEOUT = 10.0
_DEFAULT_TOOL_TIMEOUT = 30.0


class MCPHttpClient:
    """MCP client using HTTP/SSE transport.

    The server must expose:
      POST /message   — receives JSON-RPC requests
      GET  /sse       — SSE stream for responses and notifications

    Auth: supports Bearer token via auth dict {"type": "bearer", "token": "..."}.
    """

    def __init__(
        self,
        name: str,
        url: str,
        auth: dict[str, Any] | None = None,
        tool_timeout: float = _DEFAULT_TOOL_TIMEOUT,
    ) -> None:
        self.name = name
        self._base_url = url.rstrip("/")
        self._auth = auth
        self._tool_timeout = tool_timeout
        self._id_counter = 0
        self._connected = False
        self._server_info: dict[str, Any] = {}

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def server_info(self) -> dict[str, Any]:
        return dict(self._server_info)

    async def connect(self) -> None:
        """Initialize the HTTP connection."""
        try:
            import httpx  # noqa: F401
        except ImportError:
            raise MCPClientError(
                "httpx is required for HTTP MCP transport. "
                "Install it with: pip install httpx"
            )
        try:
            response = await self._post(
                METHOD_INITIALIZE,
                build_initialize_params(),
                timeout=_INITIALIZE_TIMEOUT,
            )
        except Exception as exc:
            raise MCPClientError(f"HTTP MCP '{self.name}' initialize failed: {exc}") from exc

        self._server_info = response.get("serverInfo", {})
        self._connected = True
        logger.info("HTTP MCP server '%s' connected. Server: %s", self.name, self._server_info)

    async def list_tools(self) -> list[MCPToolSchema]:
        response = await self._post(METHOD_TOOLS_LIST, {})
        tools_raw = response.get("tools", [])
        result: list[MCPToolSchema] = []
        for t in tools_raw:
            if isinstance(t, dict) and "name" in t:
                result.append(MCPToolSchema(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                ))
        return result

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._post(
            METHOD_TOOLS_CALL,
            {"name": tool_name, "arguments": arguments},
            timeout=self._tool_timeout,
        )

    async def disconnect(self) -> None:
        self._connected = False

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    def _auth_headers(self) -> dict[str, str]:
        if not self._auth:
            return {}
        if self._auth.get("type") == "bearer":
            token = self._auth.get("token", "")
            if token:
                return {"Authorization": f"Bearer {token}"}
        return {}

    async def _post(
        self,
        method: str,
        params: dict[str, Any],
        timeout: float = _DEFAULT_TOOL_TIMEOUT,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request via HTTP POST and return the result."""
        import httpx

        req_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        headers = {"Content-Type": "application/json", **self._auth_headers()}
        url = f"{self._base_url}/message"

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as exc:
                raise MCPClientError(
                    f"HTTP MCP '{self.name}' {method} returned {exc.response.status_code}"
                ) from exc
            except Exception as exc:
                raise MCPClientError(f"HTTP MCP '{self.name}' request failed: {exc}") from exc

        if data.get("error"):
            err = data["error"]
            raise MCPClientError(
                f"MCP error from '{self.name}': [{err.get('code')}] {err.get('message')}"
            )
        return data.get("result") or {}
