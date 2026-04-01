"""LSP client for language server communication — Q190, task 1062."""
from __future__ import annotations

import enum
import json
import subprocess
import threading
from typing import Any, Optional


class LSPCapability(enum.Enum):
    """Capabilities that an LSP server may advertise."""

    GOTO_DEFINITION = "textDocument/definition"
    FIND_REFERENCES = "textDocument/references"
    HOVER = "textDocument/hover"
    COMPLETION = "textDocument/completion"
    DIAGNOSTICS = "textDocument/publishDiagnostics"
    RENAME = "textDocument/rename"


class LSPClient:
    """Manages communication with a Language Server Protocol server."""

    def __init__(self, command: str, args: tuple[str, ...] = ()) -> None:
        self._command = command
        self._args = args
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._request_id = 0
        self._capabilities: frozenset[str] = frozenset()
        self._initialized = False

    @property
    def is_running(self) -> bool:
        """Return True if the server process is alive."""
        with self._lock:
            return self._process is not None and self._process.poll() is None

    @property
    def capabilities(self) -> frozenset[str]:
        """Return the set of capabilities reported by the server."""
        return self._capabilities

    def start(self) -> bool:
        """Start the language server process and perform initialization.

        Returns True if the server started and initialized successfully.
        """
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return True
            try:
                self._process = subprocess.Popen(
                    [self._command, *self._args],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except FileNotFoundError:
                return False
            except OSError:
                return False

        # Send initialize request
        try:
            response = self.send_request("initialize", {
                "processId": None,
                "capabilities": {},
                "rootUri": None,
            })
            self._capabilities = _extract_capabilities(response)
            self._initialized = True
            # Send initialized notification (no response expected)
            self._send_notification("initialized", {})
            return True
        except Exception:
            self.stop()
            return False

    def stop(self) -> None:
        """Shut down the language server and terminate the process."""
        with self._lock:
            proc = self._process
            self._process = None
            self._initialized = False
            self._capabilities = frozenset()

        if proc is not None:
            try:
                if proc.stdin:
                    proc.stdin.close()
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and return the result dict.

        Raises RuntimeError if the server is not running.
        Raises ValueError if the server returns an error response.
        """
        if not self.is_running:
            raise RuntimeError("LSP server is not running")

        with self._lock:
            self._request_id += 1
            req_id = self._request_id
            proc = self._process

        message = _encode_message({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        })

        try:
            proc.stdin.write(message)  # type: ignore[union-attr]
            proc.stdin.flush()  # type: ignore[union-attr]
            response = _read_message(proc.stdout)  # type: ignore[arg-type]
        except Exception as exc:
            raise RuntimeError(f"Communication error: {exc}") from exc

        if "error" in response:
            err = response["error"]
            raise ValueError(f"LSP error {err.get('code', '?')}: {err.get('message', 'unknown')}")

        return response.get("result", {})

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        if not self.is_running:
            return

        with self._lock:
            proc = self._process

        message = _encode_message({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        })

        try:
            proc.stdin.write(message)  # type: ignore[union-attr]
            proc.stdin.flush()  # type: ignore[union-attr]
        except Exception:
            pass


def _encode_message(body: dict[str, Any]) -> bytes:
    """Encode a JSON-RPC message with Content-Length header."""
    content = json.dumps(body).encode("utf-8")
    header = f"Content-Length: {len(content)}\r\n\r\n".encode("ascii")
    return header + content


def _read_message(stream) -> dict[str, Any]:
    """Read a JSON-RPC message from a stream."""
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            raise RuntimeError("Stream closed before headers complete")
        line_str = line.decode("ascii").strip()
        if not line_str:
            break
        if ":" in line_str:
            key, value = line_str.split(":", 1)
            headers[key.strip()] = value.strip()

    content_length = int(headers.get("Content-Length", "0"))
    if content_length <= 0:
        raise RuntimeError("Missing or invalid Content-Length header")

    body = stream.read(content_length)
    return json.loads(body.decode("utf-8"))


def _extract_capabilities(init_result: dict[str, Any]) -> frozenset[str]:
    """Extract capability names from an initialize response."""
    caps: set[str] = set()
    server_caps = init_result.get("capabilities", {})
    if not isinstance(server_caps, dict):
        return frozenset()

    mapping = {
        "definitionProvider": LSPCapability.GOTO_DEFINITION.value,
        "referencesProvider": LSPCapability.FIND_REFERENCES.value,
        "hoverProvider": LSPCapability.HOVER.value,
        "completionProvider": LSPCapability.COMPLETION.value,
        "renameProvider": LSPCapability.RENAME.value,
    }
    for key, cap_value in mapping.items():
        if server_caps.get(key):
            caps.add(cap_value)

    return frozenset(caps)
