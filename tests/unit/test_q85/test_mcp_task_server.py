"""Tests for MCPTaskServer (T560)."""
from __future__ import annotations
import asyncio
import pytest
from lidco.tools.mcp_task_server import MCPTaskServer, MCPTool, MCPTaskHandle


def make_server():
    server = MCPTaskServer()

    async def echo(message: str = "") -> str:
        return f"echo:{message}"

    server.register_tool(MCPTool(
        name="echo",
        description="Echo a message",
        input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
        handler=echo,
    ))
    return server


def test_list_tools():
    s = make_server()
    tools = s.list_tools()
    assert any(t["name"] == "echo" for t in tools)


def test_call_tool_sync():
    s = make_server()
    result = asyncio.run(s.call_tool("echo", {"message": "hello"}))
    assert result.result == "echo:hello"
    assert result.is_async is False


def test_call_unknown_tool():
    s = make_server()
    with pytest.raises(ValueError, match="Unknown tool"):
        asyncio.run(s.call_tool("nonexistent", {}))


def test_call_tool_async_returns_handle():
    s = make_server()
    result = asyncio.run(s.call_tool("echo", {"message": "hi"}, async_mode=True))
    assert result.is_async is True
    assert result.task_id is not None


def test_get_task_status():
    s = make_server()
    result = asyncio.run(s.call_tool("echo", {"message": "x"}))
    handle = s.get_task_status(result.task_id)
    assert handle is not None
    assert handle.status == "done"


def test_server_info():
    s = make_server()
    info = s.server_info()
    assert info["name"] == "lidco"
    assert info["tools"] == 1


def test_handle_message_initialize():
    s = make_server()
    resp = s.handle_message({"method": "initialize", "id": 1})
    assert "result" in resp
    assert "serverInfo" in resp["result"]


def test_handle_message_tools_list():
    s = make_server()
    resp = s.handle_message({"method": "tools/list", "id": 2})
    assert "result" in resp
    assert len(resp["result"]["tools"]) == 1


def test_handle_message_unknown_method():
    s = make_server()
    resp = s.handle_message({"method": "unknown/method", "id": 3})
    assert "error" in resp
