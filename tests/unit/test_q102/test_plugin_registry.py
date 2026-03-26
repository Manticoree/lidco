"""Tests for src/lidco/plugins/registry.py — PluginRegistry, PluginMetadata."""
import sys
import types
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from lidco.plugins.registry import (
    PluginRegistry, PluginMetadata, PluginNotFoundError,
)


class TestPluginRegistryBasic:
    def test_register_and_get(self):
        reg = PluginRegistry()
        class MyPlugin:
            pass
        reg.register("my_plugin", MyPlugin)
        assert reg.get("my_plugin") is MyPlugin

    def test_get_missing_raises(self):
        reg = PluginRegistry()
        with pytest.raises(PluginNotFoundError) as exc:
            reg.get("missing")
        assert exc.value.plugin_name == "missing"

    def test_unregister_existing(self):
        reg = PluginRegistry()
        class P:
            pass
        reg.register("p", P)
        assert reg.unregister("p") is True
        with pytest.raises(PluginNotFoundError):
            reg.get("p")

    def test_unregister_missing(self):
        reg = PluginRegistry()
        assert reg.unregister("nonexistent") is False

    def test_list(self):
        reg = PluginRegistry()
        class A: pass
        class B: pass
        reg.register("b", B)
        reg.register("a", A)
        assert reg.list() == ["a", "b"]

    def test_list_with_metadata(self):
        reg = PluginRegistry()
        class P: pass
        meta = PluginMetadata(name="p", version="1.0")
        reg.register("p", P, meta)
        items = reg.list_with_metadata()
        assert len(items) == 1
        assert items[0][0] == "p"
        assert items[0][1].version == "1.0"

    def test_len(self):
        reg = PluginRegistry()
        class P: pass
        assert len(reg) == 0
        reg.register("p", P)
        assert len(reg) == 1

    def test_contains(self):
        reg = PluginRegistry()
        class P: pass
        reg.register("p", P)
        assert "p" in reg
        assert "q" not in reg

    def test_clear(self):
        reg = PluginRegistry()
        class P: pass
        reg.register("p", P)
        reg.clear()
        assert len(reg) == 0

    def test_get_metadata(self):
        reg = PluginRegistry()
        class P: pass
        meta = PluginMetadata(name="p", version="2.0", author="Alice")
        reg.register("p", P, meta)
        m = reg.get_metadata("p")
        assert m.version == "2.0"
        assert m.author == "Alice"

    def test_get_metadata_missing(self):
        reg = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            reg.get_metadata("missing")

    def test_auto_metadata_from_name(self):
        reg = PluginRegistry()
        class P: pass
        reg.register("my_plugin", P)
        m = reg.get_metadata("my_plugin")
        assert m.name == "my_plugin"


class TestPluginRegistryLoadAll:
    def _make_temp_plugin(self, tmp_path, name, plugin_name, extra=""):
        code = f"""
class {name}:
    plugin_name = "{plugin_name}"
    plugin_version = "1.2.3"
    plugin_description = "A test plugin"
    plugin_author = "Tester"
{extra}
"""
        (tmp_path / f"{name.lower()}.py").write_text(code)

    def test_load_all_discovers_plugins(self, tmp_path):
        self._make_temp_plugin(tmp_path, "Alpha", "alpha")
        reg = PluginRegistry()
        loaded = reg.load_all(tmp_path)
        assert "alpha" in loaded
        assert "alpha" in reg

    def test_load_all_metadata(self, tmp_path):
        self._make_temp_plugin(tmp_path, "Beta", "beta")
        reg = PluginRegistry()
        reg.load_all(tmp_path)
        m = reg.get_metadata("beta")
        assert m.version == "1.2.3"
        assert m.author == "Tester"

    def test_load_all_ignores_dunder(self, tmp_path):
        (tmp_path / "__init__.py").write_text("")
        reg = PluginRegistry()
        loaded = reg.load_all(tmp_path)
        assert loaded == []

    def test_load_all_skips_bad_files(self, tmp_path):
        (tmp_path / "broken.py").write_text("def )()(: SYNTAX ERROR")
        reg = PluginRegistry()
        loaded = reg.load_all(tmp_path)
        assert loaded == []

    def test_load_all_skips_classes_without_plugin_name(self, tmp_path):
        (tmp_path / "no_name.py").write_text("class Foo: pass\n")
        reg = PluginRegistry()
        loaded = reg.load_all(tmp_path)
        assert loaded == []

    def test_load_all_multiple_plugins_in_one_file(self, tmp_path):
        code = """
class PlugA:
    plugin_name = "plugA"

class PlugB:
    plugin_name = "plugB"
"""
        (tmp_path / "multi.py").write_text(code)
        reg = PluginRegistry()
        loaded = reg.load_all(tmp_path)
        assert set(loaded) >= {"plugA", "plugB"}

    def test_load_all_returns_names(self, tmp_path):
        self._make_temp_plugin(tmp_path, "Gamma", "gamma")
        reg = PluginRegistry()
        loaded = reg.load_all(tmp_path)
        assert isinstance(loaded, list)
        assert "gamma" in loaded
