"""Context-aware code completion provider."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompletionItem:
    """A single completion item."""

    label: str
    insert_text: str
    kind: str = "text"
    detail: str = ""
    sort_priority: int = 50


class CompletionProvider:
    """Provides context-aware code completions based on known symbols."""

    def __init__(self) -> None:
        self._symbols: list[dict[str, str]] = []
        self._builtins = [
            {"name": "print", "kind": "function", "module": "builtins"},
            {"name": "len", "kind": "function", "module": "builtins"},
            {"name": "range", "kind": "function", "module": "builtins"},
            {"name": "str", "kind": "class", "module": "builtins"},
            {"name": "int", "kind": "class", "module": "builtins"},
            {"name": "list", "kind": "class", "module": "builtins"},
            {"name": "dict", "kind": "class", "module": "builtins"},
            {"name": "set", "kind": "class", "module": "builtins"},
            {"name": "tuple", "kind": "class", "module": "builtins"},
            {"name": "bool", "kind": "class", "module": "builtins"},
            {"name": "float", "kind": "class", "module": "builtins"},
            {"name": "isinstance", "kind": "function", "module": "builtins"},
            {"name": "enumerate", "kind": "function", "module": "builtins"},
            {"name": "zip", "kind": "function", "module": "builtins"},
            {"name": "map", "kind": "function", "module": "builtins"},
            {"name": "filter", "kind": "function", "module": "builtins"},
            {"name": "sorted", "kind": "function", "module": "builtins"},
            {"name": "type", "kind": "function", "module": "builtins"},
        ]
        self._common_modules = [
            "os", "sys", "json", "re", "math", "datetime", "pathlib",
            "collections", "itertools", "functools", "typing", "dataclasses",
            "enum", "abc", "io", "hashlib", "logging", "unittest", "time",
        ]
        self._type_attrs: dict[str, list[dict[str, str]]] = {
            "str": [
                {"name": "upper", "kind": "method"},
                {"name": "lower", "kind": "method"},
                {"name": "strip", "kind": "method"},
                {"name": "split", "kind": "method"},
                {"name": "join", "kind": "method"},
                {"name": "replace", "kind": "method"},
                {"name": "startswith", "kind": "method"},
                {"name": "endswith", "kind": "method"},
                {"name": "format", "kind": "method"},
                {"name": "find", "kind": "method"},
            ],
            "list": [
                {"name": "append", "kind": "method"},
                {"name": "extend", "kind": "method"},
                {"name": "insert", "kind": "method"},
                {"name": "remove", "kind": "method"},
                {"name": "pop", "kind": "method"},
                {"name": "sort", "kind": "method"},
                {"name": "reverse", "kind": "method"},
                {"name": "copy", "kind": "method"},
                {"name": "clear", "kind": "method"},
                {"name": "index", "kind": "method"},
            ],
            "dict": [
                {"name": "keys", "kind": "method"},
                {"name": "values", "kind": "method"},
                {"name": "items", "kind": "method"},
                {"name": "get", "kind": "method"},
                {"name": "update", "kind": "method"},
                {"name": "pop", "kind": "method"},
                {"name": "setdefault", "kind": "method"},
                {"name": "clear", "kind": "method"},
                {"name": "copy", "kind": "method"},
            ],
        }

    def add_symbols(self, symbols: list[dict[str, str]]) -> None:
        """Add known symbols with name/kind/module."""
        self._symbols.extend(symbols)

    def complete(self, prefix: str, context: str = "", max_items: int = 10) -> list[CompletionItem]:
        """Return completions matching prefix."""
        if not prefix:
            return []

        lower_prefix = prefix.lower()
        items: list[CompletionItem] = []

        # Search user symbols first
        for sym in self._symbols:
            name = sym.get("name", "")
            if name.lower().startswith(lower_prefix):
                kind = sym.get("kind", "text")
                module = sym.get("module", "")
                detail = f"{kind} from {module}" if module else kind
                items.append(CompletionItem(
                    label=name,
                    insert_text=name,
                    kind=kind,
                    detail=detail,
                    sort_priority=10,
                ))

        # Search builtins
        for sym in self._builtins:
            name = sym["name"]
            if name.lower().startswith(lower_prefix):
                items.append(CompletionItem(
                    label=name,
                    insert_text=name,
                    kind=sym["kind"],
                    detail=f"builtin {sym['kind']}",
                    sort_priority=30,
                ))

        # Deduplicate by label
        seen: set[str] = set()
        unique: list[CompletionItem] = []
        for item in items:
            if item.label not in seen:
                seen.add(item.label)
                unique.append(item)

        unique.sort(key=lambda c: (c.sort_priority, c.label))
        return unique[:max_items]

    def complete_import(self, partial: str) -> list[CompletionItem]:
        """Complete import module names."""
        lower = partial.lower()
        items: list[CompletionItem] = []

        for mod in self._common_modules:
            if mod.lower().startswith(lower):
                items.append(CompletionItem(
                    label=mod,
                    insert_text=f"import {mod}",
                    kind="module",
                    detail=f"stdlib module",
                    sort_priority=20,
                ))

        # Also check user symbols with kind=module
        for sym in self._symbols:
            if sym.get("kind") == "module" and sym.get("name", "").lower().startswith(lower):
                items.append(CompletionItem(
                    label=sym["name"],
                    insert_text=f"import {sym['name']}",
                    kind="module",
                    detail="user module",
                    sort_priority=15,
                ))

        items.sort(key=lambda c: (c.sort_priority, c.label))
        return items

    def complete_attribute(self, obj_type: str, prefix: str = "") -> list[CompletionItem]:
        """Complete attributes for a given object type."""
        attrs = self._type_attrs.get(obj_type, [])
        lower_prefix = prefix.lower()
        items: list[CompletionItem] = []

        for attr in attrs:
            name = attr["name"]
            if not prefix or name.lower().startswith(lower_prefix):
                items.append(CompletionItem(
                    label=name,
                    insert_text=name,
                    kind=attr.get("kind", "attribute"),
                    detail=f"{obj_type}.{name}",
                    sort_priority=20,
                ))

        items.sort(key=lambda c: c.label)
        return items

    def clear_symbols(self) -> None:
        """Remove all user-added symbols."""
        self._symbols.clear()

    def symbol_count(self) -> int:
        """Return count of user-added symbols."""
        return len(self._symbols)
