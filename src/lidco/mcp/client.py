"""MCP stdio transport client — Task 253.

Manages a single MCP server subprocess, communicating via JSON-RPC 2.0
over stdin/stdout with newline-delimited framing.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from lidco.mcp.protocol import (
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    METHOD_INITIALIZE,
    METHOD_INITIALIZED,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    build_initialize_params,
    decode_message,
    encode_notification,
    encode_request,
)

logger = logging.getLogger(__name__)

_INITIALIZE_TIMEOUT = 10.0   # seconds
_DEFAULT_TOOL_TIMEOUT = 30.0  # seconds


@dataclass
class MCPToolSchema:
    """Schema for a single tool from tools/list."""
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


class MCPClientError(Exception):
    """Raised when the MCP server returns an error or communication fails."""


class MCPClient:
    """Manages one stdio MCP server subprocess.

    Usage::

        client = MCPClient("myserver", ["npx", "@playwright/mcp"])
        await client.connect()
        tools = await client.list_tools()
        result = await client.call_tool("browser_navigate", {"url": "https://example.com"})
        await client.disconnect()
    """

    def __init__(
        self,
        name: str,
        command: list[str],
        env: dict[str, str] | None = None,
        tool_timeout: float = _DEFAULT_TOOL_TIMEOUT,
    ) -> None:
        self.name = name
        self._command = command
        self._env: dict[str, str] = {**os.environ, **(env or {})}
        self._tool_timeout = tool_timeout
        self._process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task | None = None
        self._pending: dict[int | str, asyncio.Future] = {}
        self._id_counter: int = 0
        self._connected: bool = False
        self._server_info: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected and self._process is not None

    @property
    def server_info(self) -> dict[str, Any]:
        return dict(self._server_info)

    async def connect(self) -> None:
        """Start the subprocess and complete the MCP initialize handshake."""
        if self._connected:
            return
        try:
            self._process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._env,
            )
        except (OSError, FileNotFoundError) as exc:
            raise MCPClientError(f"Failed to start MCP server '{self.name}': {exc}") from exc

        self._reader_task = asyncio.create_task(
            self._reader_loop(), name=f"mcp-reader-{self.name}"
        )

        # Initialize handshake
        try:
            await asyncio.wait_for(self._initialize(), timeout=_INITIALIZE_TIMEOUT)
        except asyncio.TimeoutError:
            await self.disconnect()
            raise MCPClientError(
                f"MCP server '{self.name}' did not respond to initialize within {_INITIALIZE_TIMEOUT}s"
            )

        self._connected = True
        logger.info("MCP server '%s' connected. Server: %s", self.name, self._server_info)

    async def list_tools(self) -> list[MCPToolSchema]:
        """Request tools/list and return parsed schemas."""
        response = await self._request(METHOD_TOOLS_LIST, {})
        tools_raw = response.get("tools", [])
        result: list[MCPToolSchema] = []
        for t in tools_raw:
            if not isinstance(t, dict) or "name" not in t:
                continue
            result.append(MCPToolSchema(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            ))
        return result

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool and return its result dict."""
        response = await self._request(
            METHOD_TOOLS_CALL,
            {"name": tool_name, "arguments": arguments},
            timeout=self._tool_timeout,
        )
        return response

    async def disconnect(self) -> None:
        """Gracefully shut down the subprocess."""
        self._connected = False

        # Cancel pending futures
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

        # Cancel reader
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await asyncio.wait_for(self._reader_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        if self._process:
            try:
                if self._process.stdin:
                    self._process.stdin.close()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass
            self._process = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    async def _initialize(self) -> None:
        """Send initialize request + notifications/initialized."""
        response = await self._request(
            METHOD_INITIALIZE,
            build_initialize_params(),
        )
        self._server_info = response.get("serverInfo", {})
        # Send initialized notification (no response expected)
        notif = JsonRpcNotification(method=METHOD_INITIALIZED)
        await self._send_raw(encode_notification(notif))

    async def _request(
        self,
        method: str,
        params: dict[str, Any],
        timeout: float = _DEFAULT_TOOL_TIMEOUT,
    ) -> dict[str, Any]:
        req_id = self._next_id()
        req = JsonRpcRequest(id=req_id, method=method, params=params)
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut

        try:
            await self._send_raw(encode_request(req))
            response = await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise MCPClientError(f"Timeout waiting for '{method}' response from '{self.name}'")
        except asyncio.CancelledError:
            self._pending.pop(req_id, None)
            raise

        if response.get("error"):
            err = response["error"]
            raise MCPClientError(
                f"MCP error from '{self.name}' method '{method}': "
                f"[{err.get('code')}] {err.get('message')}"
            )
        return response.get("result") or {}

    async def _send_raw(self, data: bytes) -> None:
        if not self._process or not self._process.stdin:
            raise MCPClientError(f"MCP server '{self.name}' is not running")
        self._process.stdin.write(data)
        await self._process.stdin.drain()

    async def _reader_loop(self) -> None:
        """Read stdout line by line, resolve pending futures."""
        if not self._process or not self._process.stdout:
            return
        try:
            async for line in self._process.stdout:
                if not line.strip():
                    continue
                try:
                    msg = decode_message(line)
                except Exception as exc:
                    logger.warning("MCP '%s' malformed response: %s | raw: %s", self.name, exc, line[:200])
                    continue

                msg_id = msg.get("id")
                # Is this a response to a pending request?
                if msg_id is not None and msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if not fut.done():
                        fut.set_result(msg)
                # Notifications have no id — log and ignore for now
                elif "method" in msg and msg_id is None:
                    logger.debug("MCP '%s' notification: %s", self.name, msg.get("method"))
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("MCP '%s' reader loop error: %s", self.name, exc)
        finally:
            # Fail all pending futures on disconnect
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(MCPClientError(f"MCP server '{self.name}' disconnected"))
            self._pending.clear()
            self._connected = False
