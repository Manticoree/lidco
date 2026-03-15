"""Tests for MCP tool adapter — Task 254."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lidco.mcp.client import MCPClientError, MCPToolSchema
from lidco.mcp.tool_adapter import (
    MCPTool,
    _json_schema_to_parameters,
    _make_tool_name,
    inject_mcp_tools,
    remove_mcp_tools,
)
from lidco.tools.base import ToolPermission, ToolResult
from lidco.tools.registry import ToolRegistry


class TestMakeToolName:
    def test_basic(self):
        assert _make_tool_name("myserver", "mytool") == "mcp__myserver__mytool"

    def test_hyphens_become_underscores(self):
        assert _make_tool_name("my-server", "my-tool") == "mcp__my_server__my_tool"

    def test_spaces_become_underscores(self):
        assert _make_tool_name("my server", "my tool") == "mcp__my_server__my_tool"


class TestJsonSchemaToParameters:
    def test_empty_schema(self):
        params = _json_schema_to_parameters({})
        assert params == []

    def test_string_param(self):
        schema = {"properties": {"path": {"type": "string", "description": "file path"}},
                  "required": ["path"]}
        params = _json_schema_to_parameters(schema)
        assert len(params) == 1
        p = params[0]
        assert p.name == "path"
        assert p.type == "string"
        assert p.required is True

    def test_optional_param(self):
        schema = {"properties": {"limit": {"type": "integer"}}}
        params = _json_schema_to_parameters(schema)
        assert params[0].required is False
        assert params[0].type == "integer"

    def test_object_becomes_string(self):
        schema = {"properties": {"options": {"type": "object"}}}
        params = _json_schema_to_parameters(schema)
        assert params[0].type == "string"

    def test_boolean_param(self):
        schema = {"properties": {"verbose": {"type": "boolean"}}}
        params = _json_schema_to_parameters(schema)
        assert params[0].type == "boolean"

    def test_array_param(self):
        schema = {"properties": {"files": {"type": "array"}}}
        params = _json_schema_to_parameters(schema)
        assert params[0].type == "array"


class TestMCPTool:
    def _make_client(self, connected=True, result=None):
        client = MagicMock()
        client.is_connected = connected
        if result is None:
            result = {"content": [{"type": "text", "text": "ok"}]}
        client.call_tool = AsyncMock(return_value=result)
        return client

    def _make_schema(self, name="list_files", desc="List files"):
        return MCPToolSchema(
            name=name,
            description=desc,
            input_schema={
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )

    def test_name_is_namespaced(self):
        client = self._make_client()
        tool = MCPTool("myserver", self._make_schema(), client)
        assert tool.name == "mcp__myserver__list_files"

    def test_description_includes_server(self):
        client = self._make_client()
        tool = MCPTool("myserver", self._make_schema(), client)
        assert "MCP:myserver" in tool.description

    def test_permission_is_ask(self):
        client = self._make_client()
        tool = MCPTool("myserver", self._make_schema(), client)
        assert tool.permission == ToolPermission.ASK

    def test_parameters_parsed(self):
        client = self._make_client()
        tool = MCPTool("myserver", self._make_schema(), client)
        assert len(tool.parameters) == 1
        assert tool.parameters[0].name == "path"

    @pytest.mark.asyncio
    async def test_run_returns_text(self):
        client = self._make_client(result={"content": [{"type": "text", "text": "hello"}]})
        tool = MCPTool("srv", self._make_schema(), client)
        result = await tool._run(path="/tmp")
        assert result.success
        assert result.output == "hello"

    @pytest.mark.asyncio
    async def test_run_not_connected(self):
        client = self._make_client(connected=False)
        tool = MCPTool("srv", self._make_schema(), client)
        result = await tool._run(path="/tmp")
        assert not result.success
        assert "not connected" in result.error

    @pytest.mark.asyncio
    async def test_run_error_result(self):
        client = self._make_client(result={"content": [{"type": "text", "text": "fail"}], "isError": True})
        tool = MCPTool("srv", self._make_schema(), client)
        result = await tool._run(path="/tmp")
        assert not result.success
        assert result.error == "fail"

    @pytest.mark.asyncio
    async def test_run_client_error(self):
        client = MagicMock()
        client.is_connected = True
        client.call_tool = AsyncMock(side_effect=MCPClientError("timeout"))
        tool = MCPTool("srv", self._make_schema(), client)
        result = await tool._run(path="/tmp")
        assert not result.success
        assert "timeout" in result.error

    @pytest.mark.asyncio
    async def test_run_image_content_placeholder(self):
        client = self._make_client(result={"content": [{"type": "image", "data": "base64..."}]})
        tool = MCPTool("srv", self._make_schema(), client)
        result = await tool._run(path="/tmp")
        assert result.success
        assert "[image data omitted]" in result.output


class TestInjectRemoveMCPTools:
    def _make_manager(self, schemas_by_server):
        manager = MagicMock()
        manager.all_tool_schemas.return_value = schemas_by_server
        clients = {}
        for name in schemas_by_server:
            c = MagicMock()
            c.is_connected = True
            clients[name] = c
        manager.get_client.side_effect = lambda n: clients.get(n)
        return manager

    def test_inject_creates_tools(self):
        schemas = [MCPToolSchema("read", "Read file", {})]
        manager = self._make_manager({"srv": schemas})
        registry = ToolRegistry()
        count = inject_mcp_tools(manager, registry)
        assert count == 1
        assert registry.get("mcp__srv__read") is not None

    def test_inject_caps_at_20(self):
        schemas = [MCPToolSchema(f"tool{i}", "", {}) for i in range(25)]
        manager = self._make_manager({"big": schemas})
        registry = ToolRegistry()
        count = inject_mcp_tools(manager, registry)
        assert count == 20

    def test_remove_mcp_tools(self):
        schemas = [MCPToolSchema("a", "", {}), MCPToolSchema("b", "", {})]
        manager = self._make_manager({"srv": schemas})
        registry = ToolRegistry()
        inject_mcp_tools(manager, registry)
        removed = remove_mcp_tools("srv", registry)
        assert removed == 2
        assert registry.get("mcp__srv__a") is None

    def test_inject_no_client_skips(self):
        manager = MagicMock()
        manager.all_tool_schemas.return_value = {"ghost": [MCPToolSchema("t", "", {})]}
        manager.get_client.return_value = None
        registry = ToolRegistry()
        count = inject_mcp_tools(manager, registry)
        assert count == 0
