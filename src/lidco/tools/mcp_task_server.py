"""MCP Task Server — expose LIDCO agents as MCP tools with async handles (MCP Nov-2025 parity)."""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]


@dataclass
class MCPTaskHandle:
    task_id: str
    tool_name: str
    status: str = "pending"    # pending | running | done | error
    result: Any = None
    error: str = ""
    progress: float = 0.0      # 0.0–1.0


@dataclass
class MCPCallResult:
    task_id: str
    result: Any
    is_async: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "result": self.result, "is_async": self.is_async}


class MCPTaskServer:
    """Minimal MCP-compatible task server.

    Exposes LIDCO tools as MCP tools. Supports both synchronous
    (immediate result) and asynchronous (task handle + polling) modes.

    The server does NOT implement HTTP transport — it provides the
    protocol logic that can be wrapped by any transport layer.
    """

    def __init__(self, server_name: str = "lidco", version: str = "1.0.0") -> None:
        self.server_name = server_name
        self.version = version
        self._tools: dict[str, MCPTool] = {}
        self._tasks: dict[str, MCPTaskHandle] = {}

    def register_tool(self, tool: MCPTool) -> None:
        """Register an MCP tool."""
        self._tools[tool.name] = tool

    def list_tools(self) -> list[dict[str, Any]]:
        """Return tool manifest (MCP tools/list response)."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        async_mode: bool = False,
    ) -> MCPCallResult:
        """Invoke a tool by name.

        In async_mode, returns a task handle immediately; poll get_task_status().
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")

        task_id = str(uuid.uuid4())[:8]
        handle = MCPTaskHandle(task_id=task_id, tool_name=name, status="running")
        self._tasks[task_id] = handle

        if async_mode:
            asyncio.create_task(self._run_async(handle, tool, arguments))
            return MCPCallResult(task_id=task_id, result={"status": "pending"}, is_async=True)

        try:
            result = await tool.handler(**arguments)
            handle.status = "done"
            handle.result = result
            handle.progress = 1.0
            return MCPCallResult(task_id=task_id, result=result, is_async=False)
        except Exception as e:
            handle.status = "error"
            handle.error = str(e)
            raise

    async def _run_async(self, handle: MCPTaskHandle, tool: MCPTool, arguments: dict[str, Any]) -> None:
        try:
            result = await tool.handler(**arguments)
            handle.status = "done"
            handle.result = result
            handle.progress = 1.0
        except Exception as e:
            handle.status = "error"
            handle.error = str(e)

    def get_task_status(self, task_id: str) -> MCPTaskHandle | None:
        return self._tasks.get(task_id)

    def server_info(self) -> dict[str, Any]:
        return {"name": self.server_name, "version": self.version, "tools": len(self._tools)}

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Synchronous JSON-RPC-style message handler for simple transports."""
        method = message.get("method", "")
        msg_id = message.get("id", 0)

        if method == "initialize":
            return {"id": msg_id, "result": {"serverInfo": self.server_info(), "capabilities": {"tools": {}}}}
        elif method == "tools/list":
            return {"id": msg_id, "result": {"tools": self.list_tools()}}
        elif method == "tasks/get":
            task_id = message.get("params", {}).get("task_id", "")
            handle = self.get_task_status(task_id)
            if handle is None:
                return {"id": msg_id, "error": {"code": -32600, "message": f"Task {task_id} not found"}}
            return {"id": msg_id, "result": {"task_id": handle.task_id, "status": handle.status, "progress": handle.progress, "result": handle.result, "error": handle.error}}
        else:
            return {"id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
