"""LSP reference finding — Q190, task 1064."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from lidco.lsp.client import LSPClient


@dataclass(frozen=True)
class Reference:
    """A reference to a symbol found by the LSP server."""

    file: str
    line: int
    column: int
    is_declaration: bool = False
    preview: str = ""


@dataclass(frozen=True)
class SymbolInfo:
    """A workspace symbol returned by the LSP server."""

    name: str
    kind: int
    file: str
    line: int
    column: int = 0
    container_name: str = ""


@dataclass(frozen=True)
class CallNode:
    """A node in a call hierarchy tree."""

    name: str
    file: str
    line: int
    column: int = 0
    children: tuple[CallNode, ...] = ()


class ReferenceFinder:
    """Find references, workspace symbols, and call hierarchies via LSP."""

    def __init__(self, client: LSPClient) -> None:
        self._client = client

    def find_references(
        self,
        file: str,
        line: int,
        col: int,
        include_declaration: bool = False,
    ) -> tuple[Reference, ...]:
        """Find all references to the symbol at the given position."""
        try:
            result = self._client.send_request("textDocument/references", {
                "textDocument": {"uri": _file_uri(file)},
                "position": {"line": line, "character": col},
                "context": {"includeDeclaration": include_declaration},
            })
        except (RuntimeError, ValueError):
            return ()

        return _parse_references(result, include_declaration)

    def find_workspace_symbols(self, query: str) -> tuple[SymbolInfo, ...]:
        """Search for symbols across the workspace."""
        try:
            result = self._client.send_request("workspace/symbol", {
                "query": query,
            })
        except (RuntimeError, ValueError):
            return ()

        return _parse_symbols(result)

    def call_hierarchy(self, file: str, line: int, col: int) -> Optional[CallNode]:
        """Build a call hierarchy tree for the symbol at the given position."""
        try:
            items = self._client.send_request("textDocument/prepareCallHierarchy", {
                "textDocument": {"uri": _file_uri(file)},
                "position": {"line": line, "character": col},
            })
        except (RuntimeError, ValueError):
            return None

        if not items or not isinstance(items, list):
            return None

        root_item = items[0]
        root = _item_to_call_node(root_item)

        # Fetch incoming calls to populate children
        try:
            incoming = self._client.send_request("callHierarchy/incomingCalls", {
                "item": root_item,
            })
        except (RuntimeError, ValueError):
            incoming = []

        if isinstance(incoming, list):
            children = tuple(
                _item_to_call_node(call.get("from", call))
                for call in incoming
                if isinstance(call, dict)
            )
            root = CallNode(
                name=root.name,
                file=root.file,
                line=root.line,
                column=root.column,
                children=children,
            )

        return root


def _file_uri(path: str) -> str:
    """Convert a file path to a file:// URI."""
    clean = path.replace("\\", "/")
    if not clean.startswith("/"):
        clean = "/" + clean
    return f"file://{clean}"


def _parse_references(result, include_declaration: bool) -> tuple[Reference, ...]:
    """Parse an LSP references response."""
    if not isinstance(result, list):
        return ()

    refs: list[Reference] = []
    for item in result:
        if not isinstance(item, dict):
            continue
        uri = item.get("uri", "")
        rng = item.get("range", {})
        start = rng.get("start", {})
        refs.append(Reference(
            file=uri.replace("file://", ""),
            line=start.get("line", 0),
            column=start.get("character", 0),
        ))

    return tuple(refs)


def _parse_symbols(result) -> tuple[SymbolInfo, ...]:
    """Parse a workspace/symbol response."""
    if not isinstance(result, list):
        return ()

    symbols: list[SymbolInfo] = []
    for item in result:
        if not isinstance(item, dict):
            continue
        loc = item.get("location", {})
        uri = loc.get("uri", "")
        rng = loc.get("range", {})
        start = rng.get("start", {})
        symbols.append(SymbolInfo(
            name=item.get("name", ""),
            kind=item.get("kind", 0),
            file=uri.replace("file://", ""),
            line=start.get("line", 0),
            column=start.get("character", 0),
            container_name=item.get("containerName", ""),
        ))

    return tuple(symbols)


def _item_to_call_node(item: dict) -> CallNode:
    """Convert a call hierarchy item dict to a CallNode."""
    uri = item.get("uri", "")
    rng = item.get("range", item.get("selectionRange", {}))
    start = rng.get("start", {})
    return CallNode(
        name=item.get("name", ""),
        file=uri.replace("file://", ""),
        line=start.get("line", 0),
        column=start.get("character", 0),
    )
