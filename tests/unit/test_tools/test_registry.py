"""Tests for tool registry."""

import pytest

from lidco.tools.registry import ToolRegistry


class TestToolRegistry:
    def test_create_default_registry(self):
        registry = ToolRegistry.create_default_registry()
        names = registry.list_names()
        assert "file_read" in names
        assert "file_write" in names
        assert "file_edit" in names
        assert "bash" in names
        assert "glob" in names
        assert "grep" in names
        assert "git" in names
        assert "ask_user" in names
        assert "web_search" in names
        assert "web_fetch" in names
        assert len(names) == 10

    def test_get_tool(self):
        registry = ToolRegistry.create_default_registry()
        tool = registry.get("file_read")
        assert tool is not None
        assert tool.name == "file_read"

    def test_get_nonexistent_tool(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_openai_schemas(self):
        registry = ToolRegistry.create_default_registry()
        schemas = registry.get_openai_schemas()
        assert len(schemas) == 10
        for schema in schemas:
            assert schema["type"] == "function"
            assert "name" in schema["function"]
            assert "parameters" in schema["function"]

    def test_filtered_schemas(self):
        registry = ToolRegistry.create_default_registry()
        schemas = registry.get_openai_schemas(["file_read", "grep"])
        assert len(schemas) == 2
        names = {s["function"]["name"] for s in schemas}
        assert names == {"file_read", "grep"}
