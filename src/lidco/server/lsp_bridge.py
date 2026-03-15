"""LSP bridge — Task 304.

Language Server Protocol adapter that exposes LIDCO capabilities to any
LSP-compatible editor (VS Code, Neovim, Emacs, etc.).

Implements a subset of LSP 3.17:
  - textDocument/completion  (code completion)
  - textDocument/hover       (explain symbol on hover)
  - textDocument/codeAction  (quick-fix / review action)
  - workspace/executeCommand (run LIDCO commands)

The bridge communicates over stdio using newline-delimited JSON-RPC 2.0
(same as the Language Server Protocol wire format).

Usage (run as a subprocess from the editor)::

    python -m lidco.server.lsp_bridge

Or programmatically::

    bridge = LspBridge(session)
    await bridge.start()  # reads from stdin, writes to stdout
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.core.session import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LSP message types
# ---------------------------------------------------------------------------

LSP_VERSION = "2.0"


# ---------------------------------------------------------------------------
# New Q64 result types (Task 431)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HoverResult:
    """Result of a hover_definitions lookup.

    Attributes:
        symbol: Symbol name found at the requested position.
        kind: Symbol kind, e.g. ``"function"``, ``"class"``, ``"variable"``.
        definition_file: Absolute path to the file containing the definition.
        definition_line: 1-based line number of the definition.
        docstring: Extracted docstring text (may be empty).
    """

    symbol: str
    kind: str
    definition_file: str
    definition_line: int
    docstring: str


@dataclass(frozen=True)
class DefinitionLocation:
    """Location of a symbol definition.

    Attributes:
        file: Absolute path to the definition file.
        line: 1-based line number.
        col: 1-based column number.
    """

    file: str
    line: int
    col: int


@dataclass(frozen=True)
class ReferenceLocation:
    """A single reference (usage) of a symbol.

    Attributes:
        file: Path to the file containing the reference.
        line: 1-based line number.
        col: 1-based column offset.
        snippet: The full source line (stripped).
    """

    file: str
    line: int
    col: int
    snippet: str


@dataclass
class LspRequest:
    """An incoming LSP JSON-RPC request."""

    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: Any = None

    @classmethod
    def from_dict(cls, data: dict) -> "LspRequest":
        return cls(
            method=str(data.get("method", "")),
            params=data.get("params") or {},
            id=data.get("id"),
        )


@dataclass
class LspResponse:
    """An outgoing LSP JSON-RPC response."""

    id: Any
    result: Any = None
    error: dict | None = None

    def to_dict(self) -> dict:
        d: dict = {"jsonrpc": LSP_VERSION, "id": self.id}
        if self.error is not None:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d


@dataclass
class LspNotification:
    """An outgoing LSP notification (no id, no response expected)."""

    method: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"jsonrpc": LSP_VERSION, "method": self.method, "params": self.params}


# ---------------------------------------------------------------------------
# Capability descriptors
# ---------------------------------------------------------------------------

SERVER_CAPABILITIES = {
    "completionProvider": {
        "resolveProvider": False,
        "triggerCharacters": [".", "(", " "],
    },
    "hoverProvider": True,
    "codeActionProvider": True,
    "executeCommandProvider": {
        "commands": [
            "lidco.review",
            "lidco.explain",
            "lidco.chat",
        ]
    },
}

SERVER_INFO = {
    "name": "lidco-lsp",
    "version": "0.1.0",
}


# ---------------------------------------------------------------------------
# Bridge implementation
# ---------------------------------------------------------------------------

class LspBridge:
    """LSP protocol bridge wrapping a LIDCO session.

    Args:
        session: Active LIDCO session for LLM calls.
        reader: Async reader for LSP messages (default: stdin).
        writer: Async writer for LSP messages (default: stdout).
    """

    def __init__(
        self,
        session: "Session | None" = None,
        reader: asyncio.StreamReader | None = None,
        writer: asyncio.StreamWriter | None = None,
    ) -> None:
        self._session = session
        self._reader = reader
        self._writer = writer
        self._initialized = False
        self._shutdown = False
        self._handlers: dict[str, Any] = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized,
            "shutdown": self._handle_shutdown,
            "exit": self._handle_exit,
            "textDocument/completion": self._handle_completion,
            "textDocument/hover": self._handle_hover,
            "textDocument/codeAction": self._handle_code_action,
            "workspace/executeCommand": self._handle_execute_command,
        }

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def _encode(self, message: dict) -> bytes:
        body = json.dumps(message, ensure_ascii=False)
        header = f"Content-Length: {len(body.encode())}\r\n\r\n"
        return (header + body).encode()

    async def _send(self, message: dict) -> None:
        if self._writer:
            self._writer.write(self._encode(message))
            await self._writer.drain()
        else:
            sys.stdout.buffer.write(self._encode(message))
            sys.stdout.buffer.flush()

    async def _recv(self) -> dict | None:
        """Read one LSP message from the stream."""
        try:
            if self._reader:
                # Read Content-Length header
                header = b""
                while not header.endswith(b"\r\n\r\n"):
                    chunk = await self._reader.read(1)
                    if not chunk:
                        return None
                    header += chunk
                content_length = 0
                for line in header.decode().split("\r\n"):
                    if line.startswith("Content-Length:"):
                        content_length = int(line.split(":", 1)[1].strip())
                body = await self._reader.readexactly(content_length)
                return json.loads(body)
            else:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                if not line:
                    return None
                return json.loads(line)
        except (EOFError, json.JSONDecodeError) as exc:
            logger.debug("LSP recv error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Run the bridge loop until shutdown or EOF."""
        logger.info("LSP bridge started")
        while not self._shutdown:
            message = await self._recv()
            if message is None:
                break
            await self._dispatch(message)

    async def _dispatch(self, message: dict) -> None:
        req = LspRequest.from_dict(message)
        handler = self._handlers.get(req.method)
        if handler is None:
            if req.id is not None:
                await self._send(
                    LspResponse(
                        id=req.id,
                        error={"code": -32601, "message": f"Method not found: {req.method}"},
                    ).to_dict()
                )
            return
        try:
            result = await handler(req)
            if req.id is not None:
                await self._send(LspResponse(id=req.id, result=result).to_dict())
        except Exception as exc:
            logger.exception("LSP handler error: %s", exc)
            if req.id is not None:
                await self._send(
                    LspResponse(
                        id=req.id,
                        error={"code": -32603, "message": str(exc)},
                    ).to_dict()
                )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _handle_initialize(self, req: LspRequest) -> dict:
        self._initialized = True
        return {
            "capabilities": SERVER_CAPABILITIES,
            "serverInfo": SERVER_INFO,
        }

    async def _handle_initialized(self, req: LspRequest) -> None:
        return None

    async def _handle_shutdown(self, req: LspRequest) -> None:
        self._shutdown = True
        return None

    async def _handle_exit(self, req: LspRequest) -> None:
        self._shutdown = True
        return None

    async def _handle_completion(self, req: LspRequest) -> dict:
        """textDocument/completion — ask the LLM for code completions."""
        if not self._session:
            return {"isIncomplete": False, "items": []}

        params = req.params
        text_doc = params.get("textDocument", {})
        position = params.get("position", {})
        file_path = text_doc.get("uri", "").removeprefix("file://")
        line = position.get("line", 0)
        char = position.get("character", 0)

        try:
            from pathlib import Path

            content = ""
            try:
                content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

            lines = content.splitlines()
            before = "\n".join(lines[:line]) + "\n" + (lines[line][:char] if line < len(lines) else "")
            after = (lines[line][char:] if line < len(lines) else "") + "\n" + "\n".join(lines[line + 1:])

            prompt = (
                f"Provide 3–5 code completions for the cursor position. "
                f"Return a JSON array of strings, nothing else.\n\n"
                f"File: {file_path}\n\n"
                f"Before cursor:\n```\n{before[-1500:]}\n```\n\n"
                f"After cursor:\n```\n{after[:500]}\n```"
            )

            from lidco.llm.base import Message

            response = await self._session.llm.complete(
                [
                    Message(role="system", content="You are a code completion assistant. Return ONLY a JSON array of completion strings."),
                    Message(role="user", content=prompt),
                ],
                max_tokens=256,
                temperature=0.0,
                role="completion",
            )

            raw = response.content.strip()
            # Extract JSON array
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1:
                completions = json.loads(raw[start : end + 1])
            else:
                completions = [raw]

            items = [
                {
                    "label": str(c),
                    "kind": 1,  # Text
                    "insertText": str(c),
                }
                for c in completions[:5]
            ]
        except Exception as exc:
            logger.warning("LSP completion error: %s", exc)
            items = []

        return {"isIncomplete": False, "items": items}

    async def _handle_hover(self, req: LspRequest) -> dict | None:
        """textDocument/hover — explain symbol under cursor."""
        if not self._session:
            return None

        params = req.params
        text_doc = params.get("textDocument", {})
        position = params.get("position", {})
        file_path = text_doc.get("uri", "").removeprefix("file://")
        line = position.get("line", 0)

        try:
            from pathlib import Path

            content = ""
            try:
                content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

            lines = content.splitlines()
            current_line = lines[line] if line < len(lines) else ""
            surrounding = "\n".join(lines[max(0, line - 3) : line + 4])

            prompt = (
                f"Briefly explain what the code on line {line + 1} does. "
                f"Be concise (1–2 sentences).\n\n"
                f"File: {file_path}\n\n"
                f"Context:\n```\n{surrounding}\n```"
            )
            response = await self._session.orchestrator.handle(
                prompt, agent_name="coder"
            )
            explanation = response.content.strip()
        except Exception as exc:
            logger.warning("LSP hover error: %s", exc)
            explanation = ""

        if not explanation:
            return None

        return {
            "contents": {"kind": "markdown", "value": explanation},
        }

    async def _handle_code_action(self, req: LspRequest) -> list:
        """textDocument/codeAction — offer review/fix actions."""
        return [
            {
                "title": "LIDCO: Review selected code",
                "kind": "quickfix",
                "command": {
                    "title": "Review",
                    "command": "lidco.review",
                    "arguments": [req.params],
                },
            },
            {
                "title": "LIDCO: Explain selected code",
                "kind": "source",
                "command": {
                    "title": "Explain",
                    "command": "lidco.explain",
                    "arguments": [req.params],
                },
            },
        ]

    async def _handle_execute_command(self, req: LspRequest) -> Any:
        """workspace/executeCommand — run lidco.* commands."""
        command = req.params.get("command", "")
        args = req.params.get("arguments", [])

        if not self._session:
            return {"error": "No session"}

        try:
            if command == "lidco.review":
                code_action_params = args[0] if args else {}
                prompt = "Review the selected code for quality, bugs, and security."
                response = await self._session.orchestrator.handle(
                    prompt, agent_name="reviewer"
                )
                return {"result": response.content}

            elif command == "lidco.explain":
                prompt = "Explain the selected code in simple terms."
                response = await self._session.orchestrator.handle(
                    prompt, agent_name="coder"
                )
                return {"result": response.content}

            elif command == "lidco.chat":
                message = args[0] if args else ""
                response = await self._session.orchestrator.handle(message)
                return {"result": response.content}

        except Exception as exc:
            logger.exception("LSP execute command error: %s", exc)
            return {"error": str(exc)}

        return {"error": f"Unknown command: {command}"}
