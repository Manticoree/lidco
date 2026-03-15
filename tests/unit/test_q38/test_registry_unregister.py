"""Tests for ToolRegistry.unregister() — added in Q38."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from lidco.tools.registry import ToolRegistry
from lidco.tools.base import BaseTool, ToolResult


class _DummyTool(BaseTool):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "dummy"

    @property
    def parameters(self):
        return []

    async def _run(self, **kwargs) -> ToolResult:
        return ToolResult(output="ok", success=True)


class TestUnregister:
    def test_unregister_existing(self):
        registry = ToolRegistry()
        tool = _DummyTool("mytool")
        registry.register(tool)
        assert registry.get("mytool") is not None

        result = registry.unregister("mytool")
        assert result is True
        assert registry.get("mytool") is None

    def test_unregister_missing_returns_false(self):
        registry = ToolRegistry()
        result = registry.unregister("nonexistent")
        assert result is False

    def test_unregister_bumps_schema_version(self):
        registry = ToolRegistry()
        registry.register(_DummyTool("a"))
        v_before = registry.schema_version
        registry.unregister("a")
        assert registry.schema_version > v_before

    def test_unregister_invalidates_cache(self):
        registry = ToolRegistry()
        registry.register(_DummyTool("a"))
        registry.register(_DummyTool("b"))
        _ = registry.get_openai_schemas()  # populate cache
        registry.unregister("a")
        schemas = registry.get_openai_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "a" not in names
        assert "b" in names

    def test_unregister_removes_from_list_names(self):
        registry = ToolRegistry()
        registry.register(_DummyTool("x"))
        registry.register(_DummyTool("y"))
        registry.unregister("x")
        assert "x" not in registry.list_names()
        assert "y" in registry.list_names()

    def test_unregister_twice_second_returns_false(self):
        registry = ToolRegistry()
        registry.register(_DummyTool("z"))
        assert registry.unregister("z") is True
        assert registry.unregister("z") is False
