"""Symbol index for cross-file lookup — Q125."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SymbolDef:
    name: str
    kind: str  # "class"/"function"/"variable"/"import"
    module: str
    line: int
    docstring: str = ""


@dataclass
class SymbolRef:
    name: str
    module: str
    line: int


class SymbolIndex:
    """Index of symbol definitions and references."""

    def __init__(self) -> None:
        self._definitions: list[SymbolDef] = []
        self._references: list[SymbolRef] = []

    def add_definition(self, sym: SymbolDef) -> None:
        self._definitions.append(sym)

    def add_reference(self, ref: SymbolRef) -> None:
        self._references.append(ref)

    def find_definition(self, name: str) -> Optional[SymbolDef]:
        """Return first matching definition."""
        for d in self._definitions:
            if d.name == name:
                return d
        return None

    def find_all_definitions(self, name: str) -> list[SymbolDef]:
        return [d for d in self._definitions if d.name == name]

    def find_references(self, name: str) -> list[SymbolRef]:
        return [r for r in self._references if r.name == name]

    def list_symbols(self, kind: str = None) -> list[SymbolDef]:
        if kind is None:
            return list(self._definitions)
        return [d for d in self._definitions if d.kind == kind]

    def list_references(self) -> list[SymbolRef]:
        return list(self._references)

    def clear(self) -> None:
        self._definitions.clear()
        self._references.clear()

    def __len__(self) -> int:
        return len(self._definitions)
