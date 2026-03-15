"""Tests for MCP JSON-RPC protocol helpers — Task 253."""

from __future__ import annotations

import json
import pytest

from lidco.mcp.protocol import (
    METHOD_INITIALIZE,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    MCP_PROTOCOL_VERSION,
    JsonRpcRequest,
    JsonRpcNotification,
    JsonRpcResponse,
    build_initialize_params,
    decode_message,
    encode_request,
)


class TestConstants:
    def test_method_names(self):
        assert METHOD_INITIALIZE == "initialize"
        assert METHOD_TOOLS_LIST == "tools/list"
        assert METHOD_TOOLS_CALL == "tools/call"

    def test_protocol_version_non_empty(self):
        assert MCP_PROTOCOL_VERSION


class TestEncodeRequest:
    def test_roundtrip(self):
        req = JsonRpcRequest(id=1, method="initialize", params={"x": 1})
        data = encode_request(req)
        parsed = json.loads(data)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == 1
        assert parsed["method"] == "initialize"
        assert parsed["params"] == {"x": 1}

    def test_newline_terminated(self):
        req = JsonRpcRequest(id=1, method="test", params={})
        data = encode_request(req)
        assert data.endswith(b"\n")


class TestDecodeMessage:
    def test_decode_response(self):
        raw = b'{"jsonrpc":"2.0","id":1,"result":{"tools":[]}}\n'
        msg = decode_message(raw)
        assert msg["id"] == 1
        assert "result" in msg

    def test_decode_notification(self):
        raw = b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
        msg = decode_message(raw)
        assert msg["method"] == "notifications/initialized"
        assert "id" not in msg or msg.get("id") is None

    def test_invalid_json_raises(self):
        with pytest.raises(Exception):
            decode_message(b"not json\n")


class TestBuildInitializeParams:
    def test_contains_protocol_version(self):
        params = build_initialize_params()
        assert "protocolVersion" in params
        assert params["protocolVersion"] == MCP_PROTOCOL_VERSION

    def test_contains_client_info(self):
        params = build_initialize_params()
        assert "clientInfo" in params
        assert "name" in params["clientInfo"]


class TestDataclasses:
    def test_jsonrpc_request(self):
        req = JsonRpcRequest(id=1, method="initialize", params={})
        assert req.jsonrpc == "2.0"

    def test_jsonrpc_notification(self):
        notif = JsonRpcNotification(method="notifications/initialized")
        assert notif.jsonrpc == "2.0"
        assert not hasattr(notif, "id") or getattr(notif, "id", None) is None

    def test_jsonrpc_response(self):
        resp = JsonRpcResponse(id=1, result={"tools": []})
        assert resp.jsonrpc == "2.0"
        assert resp.result == {"tools": []}
