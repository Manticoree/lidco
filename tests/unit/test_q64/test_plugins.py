"""Tests for PluginRegistry, LidcoPlugin, PluginLoader — Q64 Task 434."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


class TestLidcoPlugin:
    def test_abstract_base_class(self):
        from lidco.plugins.api import LidcoPlugin
        from abc import ABC
        assert issubclass(LidcoPlugin, ABC)

    def test_default_attributes(self):
        from lidco.plugins.api import LidcoPlugin
        assert LidcoPlugin.name == "unnamed_plugin"
        assert LidcoPlugin.version == "0.0.0"

    @pytest.mark.asyncio
    async def test_on_message_returns_none_by_default(self):
        from lidco.plugins.api import LidcoPlugin, PluginContext

        class MyPlugin(LidcoPlugin):
            name = "test"

        plugin = MyPlugin()
        result = await plugin.on_message("hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_on_tool_call_returns_none_by_default(self):
        from lidco.plugins.api import LidcoPlugin

        class MyPlugin(LidcoPlugin):
            name = "test"

        plugin = MyPlugin()
        result = await plugin.on_tool_call("read_file", {"path": "/tmp/x"})
        assert result is None


class TestPluginContext:
    def test_context_defaults(self):
        from lidco.plugins.api import PluginContext
        ctx = PluginContext()
        assert ctx.session is None
        assert ctx.commands is None
        assert ctx.tools is None
        assert ctx.config is None


class TestPluginRegistry:
    @pytest.mark.asyncio
    async def test_load_plugin_from_file(self, tmp_path):
        from lidco.plugins.api import PluginRegistry, LidcoPlugin
        plugin_code = """
from lidco.plugins.api import LidcoPlugin

class HelloPlugin(LidcoPlugin):
    name = "hello"
    version = "1.0.0"
"""
        plugin_file = tmp_path / "hello_plugin.py"
        plugin_file.write_text(plugin_code)
        registry = PluginRegistry()
        plugin = await registry.load(plugin_file)
        assert plugin.name == "hello"

    @pytest.mark.asyncio
    async def test_list_plugins_after_load(self, tmp_path):
        from lidco.plugins.api import PluginRegistry, LidcoPlugin
        code = """
from lidco.plugins.api import LidcoPlugin
class P1(LidcoPlugin):
    name = "p1"
"""
        f = tmp_path / "p1.py"
        f.write_text(code)
        registry = PluginRegistry()
        await registry.load(f)
        plugins = registry.list_plugins()
        assert any(p.name == "p1" for p in plugins)

    @pytest.mark.asyncio
    async def test_unload_plugin(self, tmp_path):
        from lidco.plugins.api import PluginRegistry, LidcoPlugin
        code = """
from lidco.plugins.api import LidcoPlugin
class P2(LidcoPlugin):
    name = "p2"
"""
        f = tmp_path / "p2.py"
        f.write_text(code)
        registry = PluginRegistry()
        await registry.load(f)
        await registry.unload("p2")
        assert registry.get("p2") is None

    @pytest.mark.asyncio
    async def test_load_file_not_found(self):
        from lidco.plugins.api import PluginRegistry
        registry = PluginRegistry()
        with pytest.raises(FileNotFoundError):
            await registry.load("/nonexistent/plugin.py")

    @pytest.mark.asyncio
    async def test_dispatch_message_transforms(self, tmp_path):
        from lidco.plugins.api import PluginRegistry, LidcoPlugin
        code = """
from lidco.plugins.api import LidcoPlugin
class TransformPlugin(LidcoPlugin):
    name = "transformer"
    async def on_message(self, message):
        return message.upper()
"""
        f = tmp_path / "transform.py"
        f.write_text(code)
        registry = PluginRegistry()
        await registry.load(f)
        result = await registry.dispatch_message("hello")
        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_dispatch_tool_transforms_args(self, tmp_path):
        from lidco.plugins.api import PluginRegistry, LidcoPlugin
        code = """
from lidco.plugins.api import LidcoPlugin
class ArgPlugin(LidcoPlugin):
    name = "arg_mod"
    async def on_tool_call(self, tool_name, args):
        return {**args, "modified": True}
"""
        f = tmp_path / "arg_plugin.py"
        f.write_text(code)
        registry = PluginRegistry()
        await registry.load(f)
        result = await registry.dispatch_tool("my_tool", {"path": "/tmp/x"})
        assert result.get("modified") is True


class TestPluginLoader:
    def test_discover_empty_dirs(self, tmp_path):
        from lidco.plugins.api import PluginLoader
        loader = PluginLoader(global_dir=tmp_path / "global", local_dir=tmp_path / "local")
        paths = loader.discover()
        assert paths == []

    def test_discover_finds_py_files(self, tmp_path):
        from lidco.plugins.api import PluginLoader
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "myplugin.py").write_text("# plugin")
        loader = PluginLoader(global_dir=global_dir, local_dir=tmp_path / "local")
        paths = loader.discover()
        assert any(p.name == "myplugin.py" for p in paths)

    def test_underscore_files_excluded(self, tmp_path):
        from lidco.plugins.api import PluginLoader
        d = tmp_path / "plugins"
        d.mkdir()
        (d / "_private.py").write_text("# private")
        (d / "public.py").write_text("# public")
        loader = PluginLoader(global_dir=d, local_dir=tmp_path / "local")
        paths = loader.discover()
        names = [p.name for p in paths]
        assert "_private.py" not in names
        assert "public.py" in names
