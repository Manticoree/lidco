"""Tests for lidco.auth.mcp_auth."""

from __future__ import annotations

from lidco.auth.mcp_auth import MCPAuthAdapter, MCPCredential


def test_register_and_get():
    adapter = MCPAuthAdapter()
    cred = adapter.register_credential("server1", "api_key", token="tok123")
    assert isinstance(cred, MCPCredential)
    assert cred.server_name == "server1"
    assert cred.auth_type == "api_key"
    assert adapter.get_credential("server1") is cred


def test_get_missing():
    adapter = MCPAuthAdapter()
    assert adapter.get_credential("nope") is None


def test_remove():
    adapter = MCPAuthAdapter()
    adapter.register_credential("s", "oauth", token="t")
    assert adapter.remove_credential("s") is True
    assert adapter.remove_credential("s") is False
    assert adapter.get_credential("s") is None


def test_list_servers():
    adapter = MCPAuthAdapter()
    adapter.register_credential("beta", "api_key")
    adapter.register_credential("alpha", "basic")
    assert adapter.list_servers() == ["alpha", "beta"]


def test_inject_env():
    adapter = MCPAuthAdapter()
    adapter.register_credential("my-svc", "oauth", token="abc", metadata={"region": "us"})
    env = adapter.inject_env("my-svc")
    assert env["MY_SVC_TOKEN"] == "abc"
    assert env["MY_SVC_AUTH_TYPE"] == "oauth"
    assert env["MY_SVC_REGION"] == "us"


def test_inject_env_missing():
    adapter = MCPAuthAdapter()
    assert adapter.inject_env("nope") == {}


def test_has_credential():
    adapter = MCPAuthAdapter()
    assert adapter.has_credential("x") is False
    adapter.register_credential("x", "basic")
    assert adapter.has_credential("x") is True


def test_summary_empty():
    adapter = MCPAuthAdapter()
    assert "No MCP credentials" in adapter.summary()


def test_summary_with_entries():
    adapter = MCPAuthAdapter()
    adapter.register_credential("srv1", "oauth", token="t")
    adapter.register_credential("srv2", "api_key")
    s = adapter.summary()
    assert "2 MCP credential(s)" in s
    assert "srv1" in s
    assert "srv2" in s
