"""Tool registry for managing available tools."""

from __future__ import annotations

from typing import Any

from lidco.tools.base import BaseTool


class ToolRegistry:
    """Registry for discovering and managing tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """List all tool names."""
        return list(self._tools.keys())

    def get_openai_schemas(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        """Get OpenAI function schemas for specified tools (or all)."""
        tools = (
            [self._tools[n] for n in tool_names if n in self._tools]
            if tool_names
            else list(self._tools.values())
        )
        return [t.to_openai_schema() for t in tools]

    @staticmethod
    def create_default_registry() -> ToolRegistry:
        """Create a registry with all built-in tools."""
        from lidco.tools.ask_user import AskUserTool
        from lidco.tools.bash import BashTool
        from lidco.tools.file_edit import FileEditTool
        from lidco.tools.file_read import FileReadTool
        from lidco.tools.file_write import FileWriteTool
        from lidco.tools.git import GitTool
        from lidco.tools.glob import GlobTool
        from lidco.tools.grep import GrepTool
        from lidco.tools.web_fetch import WebFetchTool
        from lidco.tools.web_search import WebSearchTool

        registry = ToolRegistry()
        for tool in [
            FileReadTool(),
            FileWriteTool(),
            FileEditTool(),
            BashTool(),
            GlobTool(),
            GrepTool(),
            GitTool(),
            AskUserTool(),
            WebSearchTool(),
            WebFetchTool(),
        ]:
            registry.register(tool)
        return registry
