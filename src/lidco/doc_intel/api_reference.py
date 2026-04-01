"""Build structured API docs from Python module source."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class APIEntry:
    """A single API documentation entry."""

    name: str
    kind: str  # "function" | "class" | "method" | "module"
    signature: str = ""
    docstring: str = ""
    module: str = ""
    line: int = 0


class APIReference:
    """Collect and render structured API documentation."""

    def __init__(self) -> None:
        self._entries: list[APIEntry] = []

    def add_entry(self, entry: APIEntry) -> None:
        """Add a single API entry."""
        self._entries.append(entry)

    def scan_source(self, source: str, module_name: str = "") -> list[APIEntry]:
        """Parse Python source and extract function/class definitions."""
        tree = ast.parse(source)
        found: list[APIEntry] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                entry = APIEntry(
                    name=node.name,
                    kind="function",
                    signature=_func_signature(node),
                    docstring=ast.get_docstring(node) or "",
                    module=module_name,
                    line=node.lineno,
                )
                found.append(entry)
                self._entries.append(entry)
            elif isinstance(node, ast.ClassDef):
                cls_entry = APIEntry(
                    name=node.name,
                    kind="class",
                    signature="",
                    docstring=ast.get_docstring(node) or "",
                    module=module_name,
                    line=node.lineno,
                )
                found.append(cls_entry)
                self._entries.append(cls_entry)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_entry = APIEntry(
                            name=f"{node.name}.{item.name}",
                            kind="method",
                            signature=_func_signature(item),
                            docstring=ast.get_docstring(item) or "",
                            module=module_name,
                            line=item.lineno,
                        )
                        found.append(method_entry)
                        self._entries.append(method_entry)
        return found

    def to_markdown(self) -> str:
        """Render all entries as Markdown."""
        if not self._entries:
            return "# API Reference\n\nNo entries."
        lines = ["# API Reference", ""]
        for entry in self._entries:
            prefix = _kind_prefix(entry.kind)
            sig = f"(`{entry.signature}`)" if entry.signature else ""
            lines.append(f"## {prefix}{entry.name} {sig}".rstrip())
            if entry.module:
                lines.append(f"*Module:* `{entry.module}` | *Line:* {entry.line}")
            if entry.docstring:
                lines.append("")
                lines.append(entry.docstring)
            lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize all entries to a dict."""
        return {
            "entries": [
                {
                    "name": e.name,
                    "kind": e.kind,
                    "signature": e.signature,
                    "docstring": e.docstring,
                    "module": e.module,
                    "line": e.line,
                }
                for e in self._entries
            ],
            "count": len(self._entries),
        }

    def by_module(self) -> dict[str, list[APIEntry]]:
        """Group entries by module name."""
        result: dict[str, list[APIEntry]] = {}
        for entry in self._entries:
            key = entry.module or "<unknown>"
            result.setdefault(key, []).append(entry)
        return result

    def entry_count(self) -> int:
        """Return the total number of entries."""
        return len(self._entries)

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _func_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Build a readable signature string from an AST function node."""
    params: list[str] = []
    for arg in node.args.args:
        hint = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
        params.append(f"{arg.arg}{hint}")
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"({', '.join(params)}){ret}"


def _kind_prefix(kind: str) -> str:
    if kind == "function":
        return "def "
    if kind == "class":
        return "class "
    if kind == "method":
        return "method "
    return ""
