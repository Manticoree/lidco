"""LIDCO as MCP server — Task 259.

Exposes LIDCO's tool registry over stdio MCP protocol so external agents
(e.g. Claude Desktop) can use LIDCO tools.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import TYPE_CHECKING, Any

from lidco.mcp.protocol import (
    ERROR_INTERNAL,
    ERROR_METHOD_NOT_FOUND,
    MCP_PROTOCOL_VERSION,
    METHOD_INITIALIZE,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    decode_message,
)

if TYPE_CHECKING:
    from lidco.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_SERVER_INFO = {
    "name": "lidco",
    "version": "1.0.0",
}


class MCPServer:
    """Exposes LIDCO tools as an MCP server over stdio.

    Usage::

        registry = ToolRegistry.create_default_registry()
        server = MCPServer(registry)
        await server.serve_stdio()  # blocks until stdin closes
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._initialized = False

    async def serve_stdio(self) -> None:
        """Read JSON-RPC requests from stdin, write responses to stdout."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        loop = asyncio.get_event_loop()

        await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)
        _, writer = await loop.connect_write_pipe(asyncio.BaseProtocol, sys.stdout.buffer)

        logger.info("LIDCO MCP server started on stdio")
        try:
            async for line in reader:
                if not line.strip():
                    continue
                try:
                    msg = decode_message(line)
                except Exception:
                    await self._write_error(writer, None, -32700, "Parse error")
                    continue

                response = await self._handle(msg)
                if response is not None:
                    await self._write_json(writer, response)
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("LIDCO MCP server stopped")

    async def _handle(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == METHOD_INITIALIZE:
            self._initialized = True
            return self._response(msg_id, {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "serverInfo": _SERVER_INFO,
                "capabilities": {"tools": {}},
            })

        if method == "notifications/initialized":
            return None  # notification, no response

        if not self._initialized:
            return self._error_response(msg_id, -32600, "Server not initialized")

        if method == METHOD_TOOLS_LIST:
            tools = []
            for tool in self._registry.list_tools():
                schema = tool.to_openai_schema()
                tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": schema.get("function", {}).get("parameters", {}),
                })
            return self._response(msg_id, {"tools": tools})

        if method == METHOD_TOOLS_CALL:
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            tool = self._registry.get(name)
            if tool is None:
                return self._error_response(msg_id, ERROR_METHOD_NOT_FOUND, f"Tool '{name}' not found")
            try:
                result = await tool.execute(**arguments)
                return self._response(msg_id, {
                    "content": [{"type": "text", "text": result.output}],
                    "isError": not result.success,
                })
            except Exception as exc:
                return self._error_response(msg_id, ERROR_INTERNAL, str(exc))

        if msg_id is not None:
            return self._error_response(msg_id, ERROR_METHOD_NOT_FOUND, f"Method '{method}' not found")
        return None  # unknown notification

    @staticmethod
    def _response(msg_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error_response(msg_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    @staticmethod
    async def _write_json(writer: Any, data: dict[str, Any]) -> None:
        line = (json.dumps(data, separators=(",", ":")) + "\n").encode("utf-8")
        writer.write(line)
        await writer.drain()

    @staticmethod
    async def _write_error(writer: Any, msg_id: Any, code: int, message: str) -> None:
        await MCPServer._write_json(writer, MCPServer._error_response(msg_id, code, message))
