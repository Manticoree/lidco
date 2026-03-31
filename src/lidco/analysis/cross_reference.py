"""Cross-reference analysis — Q125."""
from __future__ import annotations

from typing import Optional

from lidco.analysis.symbol_index2 import SymbolDef, SymbolIndex, SymbolRef


class CrossReference:
    """Find usages, definitions, and orphaned symbols."""

    def __init__(self, index: SymbolIndex) -> None:
        self._index = index

    def find_usages(self, name: str) -> list[SymbolRef]:
        """Return all references to *name*."""
        return self._index.find_references(name)

    def find_definition(self, name: str) -> Optional[SymbolDef]:
        return self._index.find_definition(name)

    def unused_definitions(self) -> list[SymbolDef]:
        """Return definitions that have no references."""
        ref_names = {r.name for r in self._index.list_references()}
        return [d for d in self._index.list_symbols() if d.name not in ref_names]

    def undefined_references(self) -> list[SymbolRef]:
        """Return references to names that are never defined."""
        def_names = {d.name for d in self._index.list_symbols()}
        return [r for r in self._index.list_references() if r.name not in def_names]

    def summary(self) -> dict:
        return {
            "defined": len(self._index),
            "referenced": len(self._index.list_references()),
            "unused": len(self.unused_definitions()),
            "undefined": len(self.undefined_references()),
        }
