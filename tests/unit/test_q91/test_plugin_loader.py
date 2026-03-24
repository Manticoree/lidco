"""Tests for ToolPluginLoader — custom tool plugin discovery and loading."""

import pytest
from pathlib import Path

from lidco.tools.plugin_loader import ToolPluginLoader, PluginInfo, PluginManifest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_register_plugin(path: Path, doc: str = "A test plugin.") -> None:
    path.write_text(f'"""{doc}"""\n\ndef register(registry):\n    pass\n')


def _write_basetool_plugin(path: Path) -> None:
    path.write_text(
        "class BaseTool:\n    pass\n\n"
        "class MyTool(BaseTool):\n    description = 'test'\n"
    )


# ---------------------------------------------------------------------------
# discover()
# ---------------------------------------------------------------------------

def test_discover_finds_project_plugins(tmp_path):
    d = tmp_path / ".lidco" / "tools"
    d.mkdir(parents=True)
    (d / "my_tool.py").write_text("def register(r): pass\n")
    loader = ToolPluginLoader(tmp_path)
    paths = loader.discover()
    assert any("my_tool" in str(p) for p in paths)


def test_discover_global_plugins(tmp_path, monkeypatch):
    global_dir = tmp_path / "home" / ".lidco" / "tools"
    global_dir.mkdir(parents=True)
    (global_dir / "global_tool.py").write_text("def register(r): pass\n")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    loader = ToolPluginLoader(tmp_path / "project")
    paths = loader.discover()
    assert any("global_tool" in str(p) for p in paths)


def test_discover_project_overrides_global(tmp_path, monkeypatch):
    global_dir = tmp_path / "home" / ".lidco" / "tools"
    global_dir.mkdir(parents=True)
    (global_dir / "tool.py").write_text("ORIGIN = 'global'\ndef register(r): pass\n")
    proj_dir = tmp_path / "proj" / ".lidco" / "tools"
    proj_dir.mkdir(parents=True)
    (proj_dir / "tool.py").write_text("ORIGIN = 'project'\ndef register(r): pass\n")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    loader = ToolPluginLoader(tmp_path / "proj")
    paths = loader.discover()
    tool_paths = [p for p in paths if p.stem == "tool"]
    assert len(tool_paths) == 1
    assert "proj" in str(tool_paths[0])


def test_discover_returns_empty_when_no_dirs(tmp_path):
    loader = ToolPluginLoader(tmp_path)
    # Neither project nor global dirs exist — should not raise
    paths = loader.discover()
    assert paths == []


def test_discover_ignores_non_py_files(tmp_path):
    d = tmp_path / ".lidco" / "tools"
    d.mkdir(parents=True)
    (d / "readme.txt").write_text("not a plugin")
    (d / "data.json").write_text("{}")
    loader = ToolPluginLoader(tmp_path)
    assert loader.discover() == []


def test_discover_sorts_deterministically(tmp_path):
    d = tmp_path / ".lidco" / "tools"
    d.mkdir(parents=True)
    for name in ["z_tool.py", "a_tool.py", "m_tool.py"]:
        (d / name).write_text("def register(r): pass\n")
    loader = ToolPluginLoader(tmp_path)
    stems = [p.stem for p in loader.discover()]
    assert stems == sorted(stems)


# ---------------------------------------------------------------------------
# validate_plugin()
# ---------------------------------------------------------------------------

def test_validate_accepts_register_function(tmp_path):
    p = tmp_path / "good.py"
    _write_register_plugin(p)
    loader = ToolPluginLoader(tmp_path)
    valid, err = loader.validate_plugin(p)
    assert valid is True
    assert err == ""


def test_validate_accepts_basetool_subclass(tmp_path):
    p = tmp_path / "good.py"
    _write_basetool_plugin(p)
    loader = ToolPluginLoader(tmp_path)
    valid, err = loader.validate_plugin(p)
    assert valid is True


def test_validate_rejects_syntax_error(tmp_path):
    p = tmp_path / "bad.py"
    p.write_text("def (invalid syntax!!!")
    loader = ToolPluginLoader(tmp_path)
    valid, err = loader.validate_plugin(p)
    assert valid is False
    assert "Parse error" in err


def test_validate_rejects_no_register_no_basetool(tmp_path):
    p = tmp_path / "nothing.py"
    p.write_text("x = 1\ny = 2\n")
    loader = ToolPluginLoader(tmp_path)
    valid, err = loader.validate_plugin(p)
    assert valid is False
    assert "register" in err or "BaseTool" in err


def test_validate_blocks_eval(tmp_path):
    p = tmp_path / "evil.py"
    p.write_text("def register(r):\n    eval('rm -rf /')\n")
    loader = ToolPluginLoader(tmp_path)
    valid, err = loader.validate_plugin(p)
    assert valid is False
    assert "eval" in err


def test_validate_blocks_exec(tmp_path):
    p = tmp_path / "evil.py"
    p.write_text("def register(r):\n    exec('x=1')\n")
    loader = ToolPluginLoader(tmp_path)
    valid, err = loader.validate_plugin(p)
    assert valid is False
    assert "exec" in err


def test_validate_blocks_compile(tmp_path):
    p = tmp_path / "evil.py"
    p.write_text("def register(r):\n    compile('x', '', 'exec')\n")
    loader = ToolPluginLoader(tmp_path)
    valid, err = loader.validate_plugin(p)
    assert valid is False
    assert "compile" in err


def test_validate_blocks_dunder_import(tmp_path):
    p = tmp_path / "evil.py"
    p.write_text("def register(r):\n    __import__('os')\n")
    loader = ToolPluginLoader(tmp_path)
    valid, err = loader.validate_plugin(p)
    assert valid is False
    assert "__import__" in err


def test_validate_blocks_os_system(tmp_path):
    p = tmp_path / "evil.py"
    p.write_text("import os\ndef register(r):\n    os.system('ls')\n")
    loader = ToolPluginLoader(tmp_path)
    valid, err = loader.validate_plugin(p)
    assert valid is False
    assert "os.system" in err


def test_validate_blocks_os_popen(tmp_path):
    p = tmp_path / "evil.py"
    p.write_text("import os\ndef register(r):\n    os.popen('ls')\n")
    loader = ToolPluginLoader(tmp_path)
    valid, err = loader.validate_plugin(p)
    assert valid is False
    assert "os.popen" in err


def test_validate_nonexistent_file(tmp_path):
    p = tmp_path / "missing.py"
    loader = ToolPluginLoader(tmp_path)
    valid, err = loader.validate_plugin(p)
    assert valid is False
    assert "Parse error" in err


# ---------------------------------------------------------------------------
# load_plugin()
# ---------------------------------------------------------------------------

def test_load_plugin_success_with_register(tmp_path):
    d = tmp_path / ".lidco" / "tools"
    d.mkdir(parents=True)
    p = d / "mytool.py"
    p.write_text('"""My tool description."""\n\ndef register(registry):\n    pass\n')
    loader = ToolPluginLoader(tmp_path)
    info = loader.load_plugin(p)
    assert info.loaded is True
    assert info.name == "mytool"
    assert info.error == ""


def test_load_plugin_picks_up_description(tmp_path):
    p = tmp_path / "desc.py"
    p.write_text('__description__ = "Custom desc"\ndef register(r): pass\n')
    loader = ToolPluginLoader(tmp_path)
    info = loader.load_plugin(p)
    assert info.loaded is True
    assert info.description == "Custom desc"


def test_load_plugin_falls_back_to_docstring(tmp_path):
    p = tmp_path / "doc.py"
    p.write_text('"""Docstring fallback."""\ndef register(r): pass\n')
    loader = ToolPluginLoader(tmp_path)
    info = loader.load_plugin(p)
    assert info.loaded is True
    assert "Docstring fallback" in info.description


def test_load_plugin_invalid_syntax_fails(tmp_path):
    p = tmp_path / "bad.py"
    p.write_text("def (invalid syntax!!!")
    loader = ToolPluginLoader(tmp_path)
    info = loader.load_plugin(p)
    assert info.loaded is False
    assert info.error != ""


def test_load_plugin_missing_register_fails(tmp_path):
    p = tmp_path / "nothing.py"
    p.write_text("x = 1\ny = 2\n")
    loader = ToolPluginLoader(tmp_path)
    info = loader.load_plugin(p)
    assert info.loaded is False
    assert "register" in info.error or "BaseTool" in info.error


def test_load_plugin_runtime_error_captured(tmp_path):
    p = tmp_path / "runtime.py"
    p.write_text("def register(r): pass\nraise RuntimeError('boom')\n")
    loader = ToolPluginLoader(tmp_path)
    info = loader.load_plugin(p)
    assert info.loaded is False
    assert "boom" in info.error


def test_load_plugin_source_path_set(tmp_path):
    p = tmp_path / "tool.py"
    _write_register_plugin(p)
    loader = ToolPluginLoader(tmp_path)
    info = loader.load_plugin(p)
    assert info.source_path == str(p)


# ---------------------------------------------------------------------------
# load_all()
# ---------------------------------------------------------------------------

def test_load_all_manifest_counts(tmp_path):
    d = tmp_path / ".lidco" / "tools"
    d.mkdir(parents=True)
    (d / "good.py").write_text("def register(r): pass\n")
    (d / "bad.py").write_text("invalid python {{{\n")
    loader = ToolPluginLoader(tmp_path)
    manifest = loader.load_all()
    assert manifest.total == 2
    assert manifest.loaded == 1
    assert manifest.failed == 1


def test_load_all_isolates_failures(tmp_path):
    d = tmp_path / ".lidco" / "tools"
    d.mkdir(parents=True)
    (d / "ok1.py").write_text("def register(r): pass\n")
    (d / "ok2.py").write_text("def register(r): pass\n")
    (d / "fail.py").write_text("SYNTAX ERROR {{{\n")
    loader = ToolPluginLoader(tmp_path)
    manifest = loader.load_all()
    assert manifest.loaded == 2


def test_load_all_empty_directory(tmp_path):
    d = tmp_path / ".lidco" / "tools"
    d.mkdir(parents=True)
    loader = ToolPluginLoader(tmp_path)
    manifest = loader.load_all()
    assert manifest.total == 0
    assert manifest.loaded == 0
    assert manifest.failed == 0


def test_load_all_no_directory(tmp_path):
    loader = ToolPluginLoader(tmp_path)
    manifest = loader.load_all()
    assert manifest.total == 0


def test_load_all_plugins_list_populated(tmp_path):
    d = tmp_path / ".lidco" / "tools"
    d.mkdir(parents=True)
    (d / "a.py").write_text("def register(r): pass\n")
    (d / "b.py").write_text("def register(r): pass\n")
    loader = ToolPluginLoader(tmp_path)
    manifest = loader.load_all()
    assert len(manifest.plugins) == 2
    assert all(isinstance(p, PluginInfo) for p in manifest.plugins)


# ---------------------------------------------------------------------------
# get_tool_from_plugin()
# ---------------------------------------------------------------------------

def test_get_tool_from_plugin_returns_instance(tmp_path):
    p = tmp_path / "mytool.py"
    p.write_text(
        "class BaseTool:\n    pass\n\n"
        "class MyTool(BaseTool):\n    description = 'test'\n"
    )
    loader = ToolPluginLoader(tmp_path)
    tool = loader.get_tool_from_plugin(p)
    assert tool is not None
    assert tool.__class__.__name__ == "MyTool"


def test_get_tool_from_plugin_returns_none_for_register_only(tmp_path):
    p = tmp_path / "reg.py"
    _write_register_plugin(p)
    loader = ToolPluginLoader(tmp_path)
    tool = loader.get_tool_from_plugin(p)
    assert tool is None


def test_get_tool_from_plugin_returns_none_for_invalid(tmp_path):
    p = tmp_path / "bad.py"
    p.write_text("SYNTAX ERROR {{{\n")
    loader = ToolPluginLoader(tmp_path)
    tool = loader.get_tool_from_plugin(p)
    assert tool is None


# ---------------------------------------------------------------------------
# PluginManifest.format_summary()
# ---------------------------------------------------------------------------

def test_manifest_format_summary():
    m = PluginManifest(plugins=[], total=5, loaded=3, failed=2)
    s = m.format_summary()
    assert "3" in s and "5" in s and "2" in s


def test_manifest_format_summary_zero():
    m = PluginManifest()
    s = m.format_summary()
    assert "0" in s


# ---------------------------------------------------------------------------
# PluginInfo dataclass
# ---------------------------------------------------------------------------

def test_plugin_info_defaults():
    info = PluginInfo(name="x", description="d", source_path="/p", loaded=True)
    assert info.error == ""
    assert info.name == "x"


def test_plugin_info_with_error():
    info = PluginInfo(name="x", description="", source_path="/p", loaded=False, error="fail")
    assert info.error == "fail"
    assert info.loaded is False
