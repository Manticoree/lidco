"""Tests for LspBridge — Task 304."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.server.lsp_bridge import (
    SERVER_CAPABILITIES,
    LspBridge,
    LspNotification,
    LspRequest,
    LspResponse,
)


# ---------------------------------------------------------------------------
# LspRequest / LspResponse dataclasses
# ---------------------------------------------------------------------------

class TestLspRequest:
    def test_from_dict_minimal(self):
        req = LspRequest.from_dict({"method": "initialize"})
        assert req.method == "initialize"
        assert req.params == {}
        assert req.id is None

    def test_from_dict_with_params_and_id(self):
        req = LspRequest.from_dict({
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": "file://main.py"}, "position": {"line": 0, "character": 0}},
            "id": 42,
        })
        assert req.id == 42
        assert "textDocument" in req.params


class TestLspResponse:
    def test_to_dict_ok(self):
        resp = LspResponse(id=1, result={"capabilities": {}})
        d = resp.to_dict()
        assert d["jsonrpc"] == "2.0"
        assert d["id"] == 1
        assert "result" in d
        assert "error" not in d

    def test_to_dict_error(self):
        resp = LspResponse(id=2, error={"code": -32601, "message": "not found"})
        d = resp.to_dict()
        assert "error" in d
        assert "result" not in d


class TestLspNotification:
    def test_to_dict(self):
        notif = LspNotification(method="window/logMessage", params={"type": 3, "message": "hi"})
        d = notif.to_dict()
        assert d["method"] == "window/logMessage"
        assert "id" not in d


# ---------------------------------------------------------------------------
# LspBridge initialization
# ---------------------------------------------------------------------------

class TestLspBridgeInit:
    def test_initialize_sets_initialized(self):
        bridge = LspBridge(session=None)
        req = LspRequest.from_dict({"method": "initialize", "id": 1, "params": {}})
        result = asyncio.run(bridge._handle_initialize(req))
        assert bridge._initialized is True
        assert "capabilities" in result
        assert "serverInfo" in result

    def test_capabilities_has_completion(self):
        assert "completionProvider" in SERVER_CAPABILITIES

    def test_capabilities_has_hover(self):
        assert SERVER_CAPABILITIES["hoverProvider"] is True

    def test_capabilities_has_code_action(self):
        assert SERVER_CAPABILITIES["codeActionProvider"] is True

    def test_shutdown_sets_flag(self):
        bridge = LspBridge()
        req = LspRequest.from_dict({"method": "shutdown", "id": 1})
        asyncio.run(bridge._handle_shutdown(req))
        assert bridge._shutdown is True


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

class TestLspBridgeDispatch:
    def _bridge_with_writer(self):
        bridge = LspBridge()
        sent = []
        async def fake_send(msg):
            sent.append(msg)
        bridge._send = fake_send
        return bridge, sent

    def test_unknown_method_with_id_sends_error(self):
        bridge, sent = self._bridge_with_writer()
        msg = {"method": "nonexistent", "id": 99, "params": {}}
        asyncio.run(bridge._dispatch(msg))
        assert len(sent) == 1
        assert sent[0]["error"]["code"] == -32601

    def test_unknown_method_without_id_no_response(self):
        bridge, sent = self._bridge_with_writer()
        msg = {"method": "nonexistent", "params": {}}  # no id
        asyncio.run(bridge._dispatch(msg))
        assert len(sent) == 0

    def test_initialize_sends_response(self):
        bridge, sent = self._bridge_with_writer()
        msg = {"method": "initialize", "id": 1, "params": {}}
        asyncio.run(bridge._dispatch(msg))
        assert len(sent) == 1
        assert "result" in sent[0]
        assert "capabilities" in sent[0]["result"]


# ---------------------------------------------------------------------------
# code_action handler
# ---------------------------------------------------------------------------

class TestLspCodeAction:
    def test_returns_review_and_explain_actions(self):
        bridge = LspBridge()
        req = LspRequest.from_dict({
            "method": "textDocument/codeAction",
            "params": {"textDocument": {"uri": "file://x.py"}, "range": {}},
            "id": 5,
        })
        result = asyncio.run(bridge._handle_code_action(req))
        titles = [a["title"] for a in result]
        assert any("Review" in t for t in titles)
        assert any("Explain" in t for t in titles)


# ---------------------------------------------------------------------------
# execute_command handler
# ---------------------------------------------------------------------------

class TestLspExecuteCommand:
    def _mock_session(self, response_content="ok"):
        session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = response_content
        session.orchestrator.handle = AsyncMock(return_value=mock_resp)
        return session

    def test_lidco_chat(self):
        bridge = LspBridge(session=self._mock_session("chat response"))
        req = LspRequest.from_dict({
            "method": "workspace/executeCommand",
            "params": {"command": "lidco.chat", "arguments": ["hello"]},
            "id": 10,
        })
        result = asyncio.run(bridge._handle_execute_command(req))
        assert result["result"] == "chat response"

    def test_unknown_command_returns_error(self):
        bridge = LspBridge(session=self._mock_session())
        req = LspRequest.from_dict({
            "method": "workspace/executeCommand",
            "params": {"command": "unknown.cmd", "arguments": []},
            "id": 11,
        })
        result = asyncio.run(bridge._handle_execute_command(req))
        assert "error" in result

    def test_no_session_returns_error(self):
        bridge = LspBridge(session=None)
        req = LspRequest.from_dict({
            "method": "workspace/executeCommand",
            "params": {"command": "lidco.chat", "arguments": ["hi"]},
            "id": 12,
        })
        result = asyncio.run(bridge._handle_execute_command(req))
        assert "error" in result

    def test_lidco_review_calls_reviewer_agent(self):
        session = self._mock_session("review done")
        bridge = LspBridge(session=session)
        req = LspRequest.from_dict({
            "method": "workspace/executeCommand",
            "params": {"command": "lidco.review", "arguments": [{}]},
            "id": 13,
        })
        result = asyncio.run(bridge._handle_execute_command(req))
        assert result["result"] == "review done"
        session.orchestrator.handle.assert_called_once()
        _, kwargs = session.orchestrator.handle.call_args
        assert kwargs.get("agent_name") == "reviewer"

    def test_lidco_explain_calls_coder_agent(self):
        session = self._mock_session("explanation here")
        bridge = LspBridge(session=session)
        req = LspRequest.from_dict({
            "method": "workspace/executeCommand",
            "params": {"command": "lidco.explain", "arguments": []},
            "id": 14,
        })
        result = asyncio.run(bridge._handle_execute_command(req))
        assert result["result"] == "explanation here"


# ---------------------------------------------------------------------------
# hover handler
# ---------------------------------------------------------------------------

class TestLspHover:
    def test_hover_returns_none_without_session(self):
        bridge = LspBridge(session=None)
        req = LspRequest.from_dict({
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": "file://x.py"}, "position": {"line": 0, "character": 0}},
            "id": 20,
        })
        result = asyncio.run(bridge._handle_hover(req))
        assert result is None

    def test_hover_returns_markdown_content(self):
        session = MagicMock()
        resp = MagicMock()
        resp.content = "This function returns the sum."
        session.orchestrator.handle = AsyncMock(return_value=resp)
        bridge = LspBridge(session=session)
        req = LspRequest.from_dict({
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": "file://x.py"}, "position": {"line": 0, "character": 0}},
            "id": 21,
        })
        result = asyncio.run(bridge._handle_hover(req))
        assert result is not None
        assert result["contents"]["kind"] == "markdown"
        assert "sum" in result["contents"]["value"]
