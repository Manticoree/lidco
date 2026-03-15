"""MCP JSON-RPC 2.0 protocol types and framing — Task 253.

MCP stdio uses newline-delimited JSON (NOT Content-Length like LSP).
Each message is a single line terminated with '\\n'.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# Protocol version string sent in initialize handshake
MCP_PROTOCOL_VERSION = "2024-11-05"

# JSON-RPC method constants
METHOD_INITIALIZE = "initialize"
METHOD_INITIALIZED = "notifications/initialized"
METHOD_TOOLS_LIST = "tools/list"
METHOD_TOOLS_CALL = "tools/call"
METHOD_PING = "ping"

# JSON-RPC standard error codes
ERROR_PARSE = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL = -32603


@dataclass(frozen=True)
class JsonRpcRequest:
    """A JSON-RPC 2.0 request (expects a response)."""
    id: int | str
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    jsonrpc: str = "2.0"


@dataclass(frozen=True)
class JsonRpcNotification:
    """A JSON-RPC 2.0 notification (no id, no response expected)."""
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    jsonrpc: str = "2.0"


@dataclass(frozen=True)
class JsonRpcResponse:
    """A JSON-RPC 2.0 response."""
    id: int | str | None
    result: Any = None
    error: dict[str, Any] | None = None
    jsonrpc: str = "2.0"


@dataclass(frozen=True)
class JsonRpcError:
    code: int
    message: str
    data: Any = None


def encode_request(req: JsonRpcRequest) -> bytes:
    """Encode a request to newline-terminated JSON bytes."""
    msg = {"jsonrpc": req.jsonrpc, "id": req.id, "method": req.method, "params": req.params}
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def encode_notification(notif: JsonRpcNotification) -> bytes:
    """Encode a notification (no id field)."""
    msg = {"jsonrpc": notif.jsonrpc, "method": notif.method, "params": notif.params}
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(line: bytes) -> dict[str, Any]:
    """Decode a newline-terminated JSON message. Raises json.JSONDecodeError on failure."""
    return json.loads(line.decode("utf-8").strip())


def build_initialize_params(client_name: str = "lidco", version: str = "1.0") -> dict[str, Any]:
    """Build the params for the initialize request."""
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "clientInfo": {"name": client_name, "version": version},
        "capabilities": {},
    }
