"""Q54/363,364,365 — ConfigReloader thread-safety, event loop, schema cache."""
from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestConfigReloaderLock:
    """Q54/363 — threading.Lock protects _mtimes."""

    def test_has_lock_attribute(self):
        from lidco.core.config_reloader import ConfigReloader
        session = MagicMock()
        session.project_dir = Path("/tmp")
        cr = ConfigReloader(session)
        assert hasattr(cr, "_lock")
        assert isinstance(cr._lock, type(threading.Lock()))

    def test_concurrent_check_does_not_raise(self, tmp_path):
        """Concurrent calls to _check() should not produce RuntimeError."""
        from lidco.core.config_reloader import ConfigReloader
        session = MagicMock()
        session.project_dir = tmp_path
        cr = ConfigReloader(session)
        errors = []

        def call_check():
            try:
                cr._check()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call_check) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3)

        assert errors == [], f"Errors in concurrent check: {errors}"


class TestSchemaVersionTracking:
    """Q54/365 — BaseAgent invalidates tool schema cache on registry version change."""

    def _make_agent(self, registry):
        from lidco.agents.base import AgentConfig, BaseAgent
        cfg = AgentConfig(name="test", description="test", system_prompt="test")

        class _TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "test"

        agent = object.__new__(_TestAgent)
        agent._config = cfg
        agent._tool_registry = registry
        agent._tool_schemas_cache = None
        agent._schema_cache_version = -1
        return agent

    def test_cache_built_on_first_call(self):
        registry = MagicMock()
        tool = MagicMock()
        tool.name = "read"
        tool.to_openai_schema.return_value = {"name": "read"}
        registry.list_tools.return_value = [tool]
        registry.schema_version = 0

        agent = self._make_agent(registry)
        schemas = agent._get_tool_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "read"

    def test_cache_invalidated_on_version_bump(self):
        registry = MagicMock()
        tool1 = MagicMock()
        tool1.name = "read"
        tool1.to_openai_schema.return_value = {"name": "read"}
        tool2 = MagicMock()
        tool2.name = "mcp__server__tool"
        tool2.to_openai_schema.return_value = {"name": "mcp__server__tool"}

        registry.list_tools.return_value = [tool1]
        registry.schema_version = 0

        agent = self._make_agent(registry)
        schemas1 = agent._get_tool_schemas()
        assert len(schemas1) == 1

        # Simulate MCP injection — version bumps, new tool added
        registry.list_tools.return_value = [tool1, tool2]
        registry.schema_version = 1

        schemas2 = agent._get_tool_schemas()
        assert len(schemas2) == 2

    def test_cache_not_rebuilt_without_version_change(self):
        registry = MagicMock()
        tool = MagicMock()
        tool.name = "read"
        tool.to_openai_schema.return_value = {"name": "read"}
        registry.list_tools.return_value = [tool]
        registry.schema_version = 5

        agent = self._make_agent(registry)
        agent._get_tool_schemas()
        agent._get_tool_schemas()  # second call

        # list_tools should be called only once
        assert registry.list_tools.call_count == 1
