"""Tests for MCPServer (LIDCO as MCP host) — Task 259."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from lidco.mcp.server import MCPServer
from lidco.mcp.protocol import METHOD_INITIALIZE, METHOD_TOOLS_LIST, METHOD_TOOLS_CALL


class _MockRegistry:
    def __init__(self, tools=None):
        self._tools = tools or []

    def list_tools(self):
        return self._tools

    def get(self, name):
        for t in self._tools:
            if t.name == name:
                return t
        return None


def _make_server(tools=None):
    registry = _MockRegistry(tools or [])
    return MCPServer(registry)


class TestMCPServerInitialize:
    @pytest.mark.asyncio
    async def test_initialize_sets_initialized(self):
        server = _make_server()
        msg = {"jsonrpc": "2.0", "id": 1, "method": METHOD_INITIALIZE, "params": {}}
        resp = await server._handle(msg)
        assert resp is not None
        assert "result" in resp
        assert resp["result"]["protocolVersion"]
        assert server._initialized

    @pytest.mark.asyncio
    async def test_not_initialized_returns_error(self):
        server = _make_server()
        msg = {"jsonrpc": "2.0", "id": 1, "method": METHOD_TOOLS_LIST, "params": {}}
        resp = await server._handle(msg)
        assert "error" in resp

    @pytest.mark.asyncio
    async def test_notifications_initialized_no_response(self):
        server = _make_server()
        # First initialize
        await server._handle({"jsonrpc": "2.0", "id": 1, "method": METHOD_INITIALIZE, "params": {}})
        # Then notification
        resp = await server._handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert resp is None


class TestMCPServerToolsList:
    @pytest.mark.asyncio
    async def test_tools_list_empty(self):
        server = _make_server()
        await server._handle({"jsonrpc": "2.0", "id": 1, "method": METHOD_INITIALIZE, "params": {}})
        msg = {"jsonrpc": "2.0", "id": 2, "method": METHOD_TOOLS_LIST, "params": {}}
        resp = await server._handle(msg)
        assert resp["result"]["tools"] == []

    @pytest.mark.asyncio
    async def test_tools_list_with_tool(self):
        tool = MagicMock()
        tool.name = "bash"
        tool.description = "Run bash"
        tool.to_openai_schema.return_value = {
            "function": {"name": "bash", "parameters": {"type": "object", "properties": {}}}
        }
        server = _make_server([tool])
        await server._handle({"jsonrpc": "2.0", "id": 1, "method": METHOD_INITIALIZE, "params": {}})
        msg = {"jsonrpc": "2.0", "id": 2, "method": METHOD_TOOLS_LIST, "params": {}}
        resp = await server._handle(msg)
        tools = resp["result"]["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "bash"
        assert tools[0]["description"] == "Run bash"


class TestMCPServerToolsCall:
    @pytest.mark.asyncio
    async def test_call_unknown_tool_returns_error(self):
        server = _make_server()
        await server._handle({"jsonrpc": "2.0", "id": 1, "method": METHOD_INITIALIZE, "params": {}})
        msg = {
            "jsonrpc": "2.0", "id": 2,
            "method": METHOD_TOOLS_CALL,
            "params": {"name": "ghost", "arguments": {}},
        }
        resp = await server._handle(msg)
        assert "error" in resp

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        from lidco.tools.base import ToolResult
        tool = MagicMock()
        tool.name = "greeter"
        tool.description = ""
        tool.to_openai_schema.return_value = {"function": {"name": "greeter", "parameters": {}}}
        tool.execute = AsyncMock(return_value=ToolResult(output="hello", success=True))

        server = _make_server([tool])
        await server._handle({"jsonrpc": "2.0", "id": 1, "method": METHOD_INITIALIZE, "params": {}})
        msg = {
            "jsonrpc": "2.0", "id": 2,
            "method": METHOD_TOOLS_CALL,
            "params": {"name": "greeter", "arguments": {}},
        }
        resp = await server._handle(msg)
        assert "result" in resp
        content = resp["result"]["content"]
        assert content[0]["text"] == "hello"
        assert resp["result"]["isError"] is False

    @pytest.mark.asyncio
    async def test_call_tool_failure_marked_as_error(self):
        from lidco.tools.base import ToolResult
        tool = MagicMock()
        tool.name = "badtool"
        tool.description = ""
        tool.to_openai_schema.return_value = {"function": {"name": "badtool", "parameters": {}}}
        tool.execute = AsyncMock(return_value=ToolResult(output="oops", success=False, error="oops"))

        server = _make_server([tool])
        await server._handle({"jsonrpc": "2.0", "id": 1, "method": METHOD_INITIALIZE, "params": {}})
        msg = {
            "jsonrpc": "2.0", "id": 2,
            "method": METHOD_TOOLS_CALL,
            "params": {"name": "badtool", "arguments": {}},
        }
        resp = await server._handle(msg)
        assert resp["result"]["isError"] is True

    @pytest.mark.asyncio
    async def test_unknown_method_returns_error(self):
        server = _make_server()
        await server._handle({"jsonrpc": "2.0", "id": 1, "method": METHOD_INITIALIZE, "params": {}})
        msg = {"jsonrpc": "2.0", "id": 2, "method": "unknown/method", "params": {}}
        resp = await server._handle(msg)
        assert "error" in resp

    @pytest.mark.asyncio
    async def test_unknown_notification_returns_none(self):
        server = _make_server()
        await server._handle({"jsonrpc": "2.0", "id": 1, "method": METHOD_INITIALIZE, "params": {}})
        # notification = no id
        msg = {"jsonrpc": "2.0", "method": "unknown/notification"}
        resp = await server._handle(msg)
        assert resp is None
