"""MCP Lazy Tool Bridge — register MCP tools as lazy stubs."""
from __future__ import annotations

from lidco.tools.lazy_registry import LazyToolRegistry


class MCPLazyToolBridge:
    """Bridge between MCP tool definitions and the lazy tool registry."""

    def __init__(self, registry: LazyToolRegistry) -> None:
        self._registry = registry
        self._mcp_schemas: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_mcp_tools(self, tools: list[dict]) -> None:
        """Register a list of MCP tool dicts as lazy stubs.

        Each dict must have at least ``name`` and ``description`` keys.
        The full dict is stored internally and resolved on demand.
        """
        for tool in tools:
            name = tool.get("name", "")
            description = tool.get("description", "")
            if not name:
                continue
            self._mcp_schemas[name] = dict(tool)
            # Capture name in closure properly
            self._registry.register_stub(
                name=name,
                description=description,
                schema_fn=self._make_schema_fn(name),
            )

    def resolve_tool(self, name: str) -> dict | None:
        """Resolve full schema for a single tool by name."""
        return self._registry.resolve(name)

    def get_minimal_context(self) -> list[dict]:
        """Return name+description only for all registered MCP tools (for system prompt)."""
        result: list[dict] = []
        for entry in self._registry.list_stubs():
            if entry.name in self._mcp_schemas:
                result.append({"name": entry.name, "description": entry.description})
        return result

    def get_full_schemas(self, tool_names: list[str]) -> list[dict]:
        """Resolve and return full schemas for the specified tools."""
        schemas: list[dict] = []
        for name in tool_names:
            schema = self._registry.resolve(name)
            if schema is not None:
                schemas.append(schema)
        return schemas

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _make_schema_fn(self, name: str):
        """Create a closure that returns the stored MCP schema for *name*."""
        def _resolve() -> dict:
            return dict(self._mcp_schemas.get(name, {}))
        return _resolve
