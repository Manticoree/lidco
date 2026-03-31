"""Tests for MCPLazyToolBridge (Task 920)."""
from __future__ import annotations

import unittest

from lidco.tools.lazy_registry import LazyToolRegistry
from lidco.mcp.lazy_tools import MCPLazyToolBridge


class TestMCPLazyToolBridge(unittest.TestCase):
    def setUp(self):
        self.registry = LazyToolRegistry()
        self.bridge = MCPLazyToolBridge(self.registry)

    def test_register_mcp_tools(self):
        tools = [
            {"name": "mcp_read", "description": "Read via MCP", "inputSchema": {"type": "object"}},
            {"name": "mcp_write", "description": "Write via MCP", "inputSchema": {"type": "object"}},
        ]
        self.bridge.register_mcp_tools(tools)
        names = self.registry.list_names()
        self.assertIn("mcp_read", names)
        self.assertIn("mcp_write", names)

    def test_register_skips_empty_name(self):
        tools = [{"name": "", "description": "bad"}]
        self.bridge.register_mcp_tools(tools)
        self.assertEqual(self.registry.list_names(), [])

    def test_resolve_tool(self):
        tools = [{"name": "t1", "description": "desc", "schema": {"type": "object"}}]
        self.bridge.register_mcp_tools(tools)
        schema = self.bridge.resolve_tool("t1")
        self.assertIsNotNone(schema)
        self.assertEqual(schema["name"], "t1")

    def test_resolve_unknown_tool(self):
        self.assertIsNone(self.bridge.resolve_tool("nope"))

    def test_get_minimal_context(self):
        tools = [
            {"name": "a", "description": "Tool A", "inputSchema": {}},
            {"name": "b", "description": "Tool B", "inputSchema": {}},
        ]
        self.bridge.register_mcp_tools(tools)
        ctx = self.bridge.get_minimal_context()
        self.assertEqual(len(ctx), 2)
        self.assertEqual(ctx[0]["name"], "a")
        self.assertNotIn("inputSchema", ctx[0])

    def test_get_full_schemas(self):
        tools = [
            {"name": "x", "description": "X", "inputSchema": {"type": "object"}},
            {"name": "y", "description": "Y", "inputSchema": {"type": "string"}},
        ]
        self.bridge.register_mcp_tools(tools)
        schemas = self.bridge.get_full_schemas(["x", "y"])
        self.assertEqual(len(schemas), 2)

    def test_get_full_schemas_partial(self):
        tools = [{"name": "x", "description": "X"}]
        self.bridge.register_mcp_tools(tools)
        schemas = self.bridge.get_full_schemas(["x", "missing"])
        self.assertEqual(len(schemas), 1)

    def test_stubs_not_resolved_until_needed(self):
        tools = [{"name": "lazy", "description": "Lazy tool"}]
        self.bridge.register_mcp_tools(tools)
        stats = self.registry.stats()
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["resolved"], 0)

        self.bridge.resolve_tool("lazy")
        stats = self.registry.stats()
        self.assertEqual(stats["resolved"], 1)


if __name__ == "__main__":
    unittest.main()
