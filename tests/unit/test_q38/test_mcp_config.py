"""Tests for MCP config loading — Task 257."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from lidco.mcp.config import MCPConfig, MCPServerEntry, load_mcp_config


class TestMCPServerEntry:
    def test_defaults(self):
        e = MCPServerEntry(name="srv")
        assert e.transport == "stdio"
        assert e.enabled is True
        assert e.timeout == 30.0
        assert e.is_stdio
        assert not e.is_http

    def test_http_transport(self):
        e = MCPServerEntry(name="remote", url="http://localhost:8080", transport="sse")
        assert e.is_http
        assert not e.is_stdio

    def test_command_list(self):
        e = MCPServerEntry(name="srv", command=["npx", "server"])
        assert e.command == ["npx", "server"]


class TestMCPConfig:
    def test_enabled_servers_filters_disabled(self):
        cfg = MCPConfig(servers=[
            MCPServerEntry(name="a", enabled=True),
            MCPServerEntry(name="b", enabled=False),
        ])
        enabled = cfg.enabled_servers()
        assert len(enabled) == 1
        assert enabled[0].name == "a"

    def test_get_server(self):
        cfg = MCPConfig(servers=[MCPServerEntry(name="x")])
        assert cfg.get_server("x") is not None
        assert cfg.get_server("missing") is None

    def test_empty_config(self):
        cfg = MCPConfig()
        assert cfg.servers == []
        assert cfg.enabled_servers() == []


class TestLoadMCPConfig:
    def test_loads_project_config(self, tmp_path: Path):
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        (lidco_dir / "mcp.json").write_text(
            json.dumps({"servers": [{"name": "proj", "command": ["echo"]}]}),
            encoding="utf-8",
        )
        cfg = load_mcp_config(tmp_path)
        assert len(cfg.servers) == 1
        assert cfg.servers[0].name == "proj"

    def test_empty_when_no_files(self, tmp_path: Path):
        cfg = load_mcp_config(tmp_path)
        assert cfg.servers == []

    def test_project_overrides_user_same_name(self, tmp_path: Path, monkeypatch):
        """Project-level entry with same name wins over user-level."""
        user_dir = tmp_path / "user_lidco"
        user_dir.mkdir()
        user_mcp = user_dir / "mcp.json"
        user_mcp.write_text(
            json.dumps({"servers": [{"name": "srv", "command": ["user-cmd"]}]}),
            encoding="utf-8",
        )

        proj_dir = tmp_path / "project"
        proj_dir.mkdir()
        (proj_dir / ".lidco").mkdir()
        (proj_dir / ".lidco" / "mcp.json").write_text(
            json.dumps({"servers": [{"name": "srv", "command": ["proj-cmd"]}]}),
            encoding="utf-8",
        )

        import lidco.mcp.config as cfg_mod
        monkeypatch.setattr(cfg_mod, "_USER_MCP_PATH", user_mcp)
        cfg = load_mcp_config(proj_dir)
        assert len(cfg.servers) == 1
        assert cfg.servers[0].command == ["proj-cmd"]

    def test_user_and_project_merged(self, tmp_path: Path, monkeypatch):
        """Servers with different names are merged."""
        user_dir = tmp_path / "user_lidco"
        user_dir.mkdir()
        user_mcp = user_dir / "mcp.json"
        user_mcp.write_text(
            json.dumps({"servers": [{"name": "user-srv", "command": ["a"]}]}),
            encoding="utf-8",
        )

        proj_dir = tmp_path / "project"
        proj_dir.mkdir()
        (proj_dir / ".lidco").mkdir()
        (proj_dir / ".lidco" / "mcp.json").write_text(
            json.dumps({"servers": [{"name": "proj-srv", "command": ["b"]}]}),
            encoding="utf-8",
        )

        import lidco.mcp.config as cfg_mod
        monkeypatch.setattr(cfg_mod, "_USER_MCP_PATH", user_mcp)
        cfg = load_mcp_config(proj_dir)
        names = {s.name for s in cfg.servers}
        assert names == {"user-srv", "proj-srv"}

    def test_invalid_entry_skipped(self, tmp_path: Path):
        """Entries missing required 'name' field are skipped with warning."""
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        (lidco_dir / "mcp.json").write_text(
            json.dumps({"servers": [{"command": ["no-name"]}, {"name": "ok"}]}),
            encoding="utf-8",
        )
        cfg = load_mcp_config(tmp_path)
        assert len(cfg.servers) == 1
        assert cfg.servers[0].name == "ok"
