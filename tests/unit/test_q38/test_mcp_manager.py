"""Tests for MCPManager — Task 253."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lidco.mcp.config import MCPConfig, MCPServerEntry
from lidco.mcp.manager import MCPManager, ServerStatus


class TestServerStatus:
    def test_defaults(self):
        s = ServerStatus(name="srv", transport="stdio")
        assert not s.connected
        assert s.tool_count == 0
        assert s.last_error == ""
        assert s.connected_at is None


class TestMCPManager:
    def _make_entry(self, name="srv", command=None, transport="stdio"):
        return MCPServerEntry(
            name=name,
            command=command or ["echo"],
            transport=transport,
        )

    def test_initial_state(self):
        m = MCPManager()
        assert m.server_names() == []
        assert m.all_tool_schemas() == {}
        assert m.get_status() == {}

    @pytest.mark.asyncio
    async def test_start_http_server_skipped(self):
        m = MCPManager()
        entry = self._make_entry(transport="sse")
        result = await m._connect_server(entry)
        assert result is False
        status = m.get_status("srv")
        assert "srv" in status

    @pytest.mark.asyncio
    async def test_start_no_command_fails(self):
        m = MCPManager()
        entry = MCPServerEntry(name="empty")
        result = await m._connect_server(entry)
        assert result is False

    @pytest.mark.asyncio
    async def test_start_all_connects_stdio(self):
        m = MCPManager()
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.is_connected = True

        with patch("lidco.mcp.manager.MCPClient", return_value=mock_client):
            cfg = MCPConfig(servers=[self._make_entry("srv")])
            await m.start_all(cfg)

        assert "srv" in m.server_names()
        assert m.is_connected("srv")

    @pytest.mark.asyncio
    async def test_stop_all_clears_state(self):
        m = MCPManager()
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.disconnect = AsyncMock()
        mock_client.is_connected = True

        with patch("lidco.mcp.manager.MCPClient", return_value=mock_client):
            cfg = MCPConfig(servers=[self._make_entry("srv")])
            await m.start_all(cfg)

        await m.stop_all()
        assert m.server_names() == []
        assert m.all_tool_schemas() == {}

    @pytest.mark.asyncio
    async def test_stop_single_server(self):
        m = MCPManager()
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.disconnect = AsyncMock()
        mock_client.is_connected = True

        with patch("lidco.mcp.manager.MCPClient", return_value=mock_client):
            cfg = MCPConfig(servers=[self._make_entry("a"), self._make_entry("b")])
            await m.start_all(cfg)

        await m.stop_server("a")
        assert "a" not in m.server_names()
        assert "b" in m.server_names()

    def test_get_status_single(self):
        m = MCPManager()
        m._statuses["srv"] = ServerStatus(name="srv", transport="stdio", connected=True)
        result = m.get_status("srv")
        assert "srv" in result

    def test_get_status_missing(self):
        m = MCPManager()
        assert m.get_status("missing") == {}

    def test_update_config_diff(self):
        m = MCPManager()
        old = MCPConfig(servers=[MCPServerEntry(name="a"), MCPServerEntry(name="b")])
        new = MCPConfig(servers=[MCPServerEntry(name="b"), MCPServerEntry(name="c")])
        removed, added = m.update_config(old, new)
        assert "a" in removed
        assert "c" in added
        assert "b" not in removed
        assert "b" not in added

    def test_is_connected_false_for_unknown(self):
        m = MCPManager()
        assert not m.is_connected("unknown")
