"""LSP definition resolution — Q190, task 1063."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lidco.lsp.client import LSPClient


@dataclass(frozen=True)
class Location:
    """A source code location returned by the LSP server."""

    file: str
    line: int
    column: int
    preview: str = ""


class DefinitionResolver:
    """Resolve go-to-definition, type-definition, and implementation via LSP."""

    def __init__(self, client: LSPClient) -> None:
        self._client = client

    def goto_definition(self, file: str, line: int, col: int) -> Optional[Location]:
        """Return the definition location for the symbol at the given position."""
        try:
            result = self._client.send_request("textDocument/definition", {
                "textDocument": {"uri": _file_uri(file)},
                "position": {"line": line, "character": col},
            })
        except (RuntimeError, ValueError):
            return None

        return _parse_single_location(result)

    def goto_type_definition(self, file: str, line: int, col: int) -> Optional[Location]:
        """Return the type-definition location for the symbol at the given position."""
        try:
            result = self._client.send_request("textDocument/typeDefinition", {
                "textDocument": {"uri": _file_uri(file)},
                "position": {"line": line, "character": col},
            })
        except (RuntimeError, ValueError):
            return None

        return _parse_single_location(result)

    def goto_implementation(self, file: str, line: int, col: int) -> list[Location]:
        """Return implementation locations for the symbol at the given position."""
        try:
            result = self._client.send_request("textDocument/implementation", {
                "textDocument": {"uri": _file_uri(file)},
                "position": {"line": line, "character": col},
            })
        except (RuntimeError, ValueError):
            return []

        return _parse_location_list(result)


def _file_uri(path: str) -> str:
    """Convert a file path to a file:// URI."""
    clean = path.replace("\\", "/")
    if not clean.startswith("/"):
        clean = "/" + clean
    return f"file://{clean}"


def _parse_single_location(result) -> Optional[Location]:
    """Parse an LSP location result into a Location or None."""
    if result is None:
        return None

    if isinstance(result, list):
        if not result:
            return None
        result = result[0]

    if not isinstance(result, dict):
        return None

    return _dict_to_location(result)


def _parse_location_list(result) -> list[Location]:
    """Parse an LSP location array result into a list of Location."""
    if result is None:
        return []

    if isinstance(result, dict):
        loc = _dict_to_location(result)
        return [loc] if loc else []

    if isinstance(result, list):
        locations = []
        for item in result:
            loc = _dict_to_location(item)
            if loc is not None:
                locations.append(loc)
        return locations

    return []


def _dict_to_location(d: dict) -> Optional[Location]:
    """Convert a raw LSP Location dict to a Location dataclass."""
    try:
        uri = d.get("uri", "")
        pos = d.get("range", {}).get("start", {})
        line = pos.get("line", 0)
        character = pos.get("character", 0)
        file_path = uri.replace("file://", "")
        return Location(file=file_path, line=line, column=character)
    except (KeyError, TypeError, AttributeError):
        return None
