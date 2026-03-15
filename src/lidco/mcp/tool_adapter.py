"""MCP tool adapter — Task 254.

Converts MCP tool schemas into BaseTool instances and injects them
into a ToolRegistry with namespace 'mcp__<server>__<tool>'.
"""

from __future__ import annotations

import logging
from typing import Any

from lidco.mcp.client import MCPClient, MCPClientError, MCPToolSchema
from lidco.mcp.manager import MCPManager
from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult
from lidco.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_MCP_TOOL_PREFIX = "mcp__"
_MAX_TOOLS_PER_SERVER = 20


def _make_tool_name(server_name: str, tool_name: str) -> str:
    """Build namespaced tool name: mcp__<server>__<tool>."""
    # Sanitize: replace hyphens/spaces with underscores
    safe_server = server_name.replace("-", "_").replace(" ", "_")
    safe_tool = tool_name.replace("-", "_").replace(" ", "_")
    return f"{_MCP_TOOL_PREFIX}{safe_server}__{safe_tool}"


def _json_schema_to_parameters(input_schema: dict[str, Any]) -> list[ToolParameter]:
    """Convert MCP inputSchema (JSON Schema) to list[ToolParameter].

    Handles flat properties. Nested 'object' params are passed as JSON strings.
    """
    props = input_schema.get("properties", {})
    required_fields: set[str] = set(input_schema.get("required", []))
    params: list[ToolParameter] = []

    for name, schema in props.items():
        if not isinstance(schema, dict):
            continue
        raw_type = schema.get("type", "string")
        # Map JSON Schema types to ToolParameter types
        if raw_type == "integer":
            param_type = "integer"
        elif raw_type == "boolean":
            param_type = "boolean"
        elif raw_type == "array":
            param_type = "array"
        elif raw_type == "object":
            param_type = "string"  # serialized as JSON string
        else:
            param_type = "string"

        params.append(ToolParameter(
            name=name,
            type=param_type,
            description=schema.get("description", ""),
            required=name in required_fields,
        ))

    return params


class MCPTool(BaseTool):
    """A BaseTool that delegates execution to an MCP server tool call.

    The tool name uses the namespace 'mcp__<server>__<original_tool>'.
    """

    def __init__(
        self,
        server_name: str,
        schema: MCPToolSchema,
        client: MCPClient,
    ) -> None:
        self._server_name = server_name
        self._original_name = schema.name
        self._namespaced_name = _make_tool_name(server_name, schema.name)
        self._description = schema.description
        self._parameters = _json_schema_to_parameters(schema.input_schema)
        self._client = client

    @property
    def name(self) -> str:
        return self._namespaced_name

    @property
    def description(self) -> str:
        desc = self._description or f"MCP tool '{self._original_name}' from server '{self._server_name}'"
        return f"[MCP:{self._server_name}] {desc}"

    @property
    def parameters(self) -> list[ToolParameter]:
        return self._parameters

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK  # always ask for external tool calls

    async def _run(self, **kwargs: Any) -> ToolResult:
        if not self._client.is_connected:
            return ToolResult(
                output="",
                success=False,
                error=f"MCP server '{self._server_name}' is not connected",
            )
        try:
            result = await self._client.call_tool(self._original_name, kwargs)
        except MCPClientError as exc:
            return ToolResult(output="", success=False, error=str(exc))

        # MCP tool results can have a 'content' list or a plain value
        content = result.get("content", [])
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
                    elif item.get("type") == "image":
                        parts.append("[image data omitted]")
                    else:
                        parts.append(str(item))
                else:
                    parts.append(str(item))
            output = "\n".join(parts)
        elif isinstance(content, str):
            output = content
        else:
            output = str(result)

        is_error = bool(result.get("isError"))
        return ToolResult(
            output=output,
            success=not is_error,
            error=output if is_error else None,
        )


def inject_mcp_tools(manager: MCPManager, registry: ToolRegistry) -> int:
    """Create MCPTool instances from manager's schemas and register them.

    Returns the number of tools injected.
    """
    count = 0
    for server_name, schemas in manager.all_tool_schemas().items():
        client = manager.get_client(server_name)
        if client is None:
            continue

        capped = schemas[:_MAX_TOOLS_PER_SERVER]
        if len(schemas) > _MAX_TOOLS_PER_SERVER:
            logger.warning(
                "MCP server '%s' has %d tools; capping at %d",
                server_name, len(schemas), _MAX_TOOLS_PER_SERVER,
            )

        for schema in capped:
            tool = MCPTool(server_name=server_name, schema=schema, client=client)
            registry.register(tool)
            count += 1

    if count:
        logger.info("Injected %d MCP tool(s) into registry", count)
    return count


def remove_mcp_tools(server_name: str, registry: ToolRegistry) -> int:
    """Unregister all MCP tools for a given server. Returns count removed."""
    prefix = _make_tool_name(server_name, "")  # "mcp__<server>__"
    names = [n for n in registry.list_names() if n.startswith(prefix)]
    for name in names:
        registry.unregister(name)
    return len(names)
