"""MCP (Model Context Protocol) support for LIDCO."""

from lidco.mcp.config import MCPConfig, MCPServerEntry, load_mcp_config
from lidco.mcp.manager import MCPManager
from lidco.mcp.tool_adapter import MCPTool, inject_mcp_tools

__all__ = [
    "MCPConfig",
    "MCPServerEntry",
    "MCPManager",
    "MCPTool",
    "inject_mcp_tools",
    "load_mcp_config",
]
