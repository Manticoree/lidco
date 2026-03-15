"""Tests for MCPHttpClient — Task 255."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lidco.mcp.client import MCPClientError, MCPToolSchema
from lidco.mcp.http_client import MCPHttpClient


class TestMCPHttpClientInit:
    def test_init_state(self):
        client = MCPHttpClient(name="srv", url="http://localhost:8080/")
        assert client.name == "srv"
        assert not client.is_connected
        assert client.server_info == {}

    def test_trailing_slash_stripped(self):
        client = MCPHttpClient(name="srv", url="http://localhost:8080/")
        assert not client._base_url.endswith("/")


class TestMCPHttpClientAuthHeaders:
    def test_no_auth(self):
        client = MCPHttpClient("srv", "http://x")
        assert client._auth_headers() == {}

    def test_bearer_token(self):
        client = MCPHttpClient("srv", "http://x", auth={"type": "bearer", "token": "tok123"})
        headers = client._auth_headers()
        assert headers["Authorization"] == "Bearer tok123"

    def test_bearer_empty_token(self):
        client = MCPHttpClient("srv", "http://x", auth={"type": "bearer", "token": ""})
        assert "Authorization" not in client._auth_headers()

    def test_unknown_auth_type(self):
        client = MCPHttpClient("srv", "http://x", auth={"type": "oauth"})
        assert client._auth_headers() == {}


class TestMCPHttpClientConnect:
    @pytest.mark.asyncio
    async def test_connect_no_httpx_raises(self):
        """When httpx is not available, connect() raises MCPClientError."""
        client = MCPHttpClient("srv", "http://localhost:8080")
        # Patch the import inside connect() to simulate httpx not being installed
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "httpx":
                raise ImportError("No module named 'httpx'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises((MCPClientError, ImportError)):
                await client.connect()

    @pytest.mark.asyncio
    async def test_connect_success(self):
        client = MCPHttpClient("srv", "http://localhost:8080")

        # _post returns data.get("result") or {}, so json() must wrap in "result"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"result": {"serverInfo": {"name": "test-server"}}}

        mock_async_client = MagicMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_async_client):
            await client.connect()

        assert client.is_connected
        assert client.server_info == {"name": "test-server"}

    @pytest.mark.asyncio
    async def test_disconnect_clears_connected(self):
        client = MCPHttpClient("srv", "http://localhost:8080")
        client._connected = True
        await client.disconnect()
        assert not client.is_connected


class TestMCPHttpClientListTools:
    @pytest.mark.asyncio
    async def test_list_tools(self):
        client = MCPHttpClient("srv", "http://localhost:8080")
        client._connected = True

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "result": {"tools": [{"name": "t1", "description": "Tool 1", "inputSchema": {}}]},
        }

        mock_async_client = MagicMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_async_client):
            tools = await client.list_tools()

        assert len(tools) == 1
        assert tools[0].name == "t1"
