"""Tests for tool registry."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

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
        assert "run_profiler" in names
        assert "run_tests" in names
        assert "rename_symbol" in names
        assert "find_test_gaps" in names
        assert "arch_diagram" in names
        assert "gh_pr" in names
        # New debug tools added in Q19-Q22
        assert "run_debug_cycle" in names
        assert "run_static_analysis" in names
        assert "check_ast_bugs" in names
        assert "capture_failure_locals" in names
        assert "check_regressions" in names
        assert "generate_minimal_repro" in names
        # Q23 import analysis + dependency checking
        assert "analyze_imports" in names
        assert "check_dependencies" in names
        # Q24 flaky test intelligence
        assert "flake_guard" in names
        # Q25 coverage-guided debug intelligence
        assert "coverage_guard" in names
        # Q26 execution trace recorder
        assert "capture_execution_trace" in names
        # Q59 code execution & runtime
        assert "code_runner" in names
        assert "docker_sandbox" in names
        assert len(names) == 31

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
        assert len(schemas) == 31
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


class TestSchemaCache:
    """Schema caching and version tracking."""

    def _mock_tool(self, name: str) -> MagicMock:
        tool = MagicMock()
        tool.name = name
        tool.to_openai_schema.return_value = {
            "type": "function",
            "function": {"name": name, "parameters": {}},
        }
        return tool

    def test_schema_version_starts_at_zero(self) -> None:
        registry = ToolRegistry()
        assert registry.schema_version == 0

    def test_schema_version_increments_on_register(self) -> None:
        registry = ToolRegistry()
        registry.register(self._mock_tool("tool_a"))
        assert registry.schema_version == 1
        registry.register(self._mock_tool("tool_b"))
        assert registry.schema_version == 2

    def test_schemas_are_cached(self) -> None:
        registry = ToolRegistry()
        tool = self._mock_tool("cached_tool")
        registry.register(tool)

        _ = registry.get_openai_schemas()
        _ = registry.get_openai_schemas()

        # to_openai_schema should be called once (first call) and cached after
        assert tool.to_openai_schema.call_count == 1

    def test_cache_invalidated_on_register(self) -> None:
        registry = ToolRegistry()
        tool_a = self._mock_tool("tool_a")
        tool_b = self._mock_tool("tool_b")

        registry.register(tool_a)
        s1 = registry.get_openai_schemas()  # builds + caches
        assert len(s1) == 1

        registry.register(tool_b)  # must invalidate cache
        s2 = registry.get_openai_schemas()  # rebuilds from scratch
        assert len(s2) == 2

        # tool_a.to_openai_schema called twice: once for s1, once for s2
        assert tool_a.to_openai_schema.call_count == 2

    def test_filtered_request_bypasses_cache(self) -> None:
        registry = ToolRegistry()
        tool_a = self._mock_tool("tool_a")
        tool_b = self._mock_tool("tool_b")
        registry.register(tool_a)
        registry.register(tool_b)

        # Populate cache for unfiltered call
        registry.get_openai_schemas()
        # Filtered call should not use cache and must not affect call count tracking
        filtered = registry.get_openai_schemas(["tool_a"])
        assert len(filtered) == 1

    def test_returned_list_is_a_copy(self) -> None:
        """Mutating the returned list must not corrupt the cache."""
        registry = ToolRegistry()
        registry.register(self._mock_tool("t"))

        schemas = registry.get_openai_schemas()
        schemas.clear()  # mutate the returned list

        # Cache should still return the original entry
        assert len(registry.get_openai_schemas()) == 1

    def test_schema_version_not_incremented_on_read(self) -> None:
        registry = ToolRegistry()
        registry.register(self._mock_tool("t"))
        v = registry.schema_version
        registry.get_openai_schemas()
        assert registry.schema_version == v
