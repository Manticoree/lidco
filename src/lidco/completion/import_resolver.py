"""Import resolution and suggestion."""
from __future__ import annotations

import re


class ImportResolver:
    """Resolve symbols to import paths and detect missing imports."""

    def __init__(self) -> None:
        self._modules: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Module registration
    # ------------------------------------------------------------------

    def add_module(self, name: str, exports: list[str]) -> None:
        """Register a module with its exported symbols."""
        self._modules = {**self._modules, name: list(exports)}

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, symbol: str) -> list[str]:
        """Return all module paths that export *symbol*."""
        results: list[str] = []
        for mod, exports in self._modules.items():
            if symbol in exports:
                results.append(mod)
        return sorted(results)

    def suggest(self, symbol: str) -> str | None:
        """Return the best ``from ... import ...`` statement for *symbol*, or ``None``."""
        paths = self.resolve(symbol)
        if not paths:
            return None
        # Prefer shortest path (most specific)
        best = min(paths, key=len)
        return f"from {best} import {symbol}"

    # ------------------------------------------------------------------
    # Missing-import detection
    # ------------------------------------------------------------------

    def detect_missing(self, source: str, known_imports: set[str] | None = None) -> list[str]:
        """Return names used in *source* that are not in *known_imports* but are resolvable."""
        if known_imports is None:
            known_imports = set()

        # Extract simple name references (very rough heuristic)
        names = set(re.findall(r"\b([A-Z][A-Za-z0-9_]*)\b", source))

        missing: list[str] = []
        for name in sorted(names):
            if name in known_imports:
                continue
            if self.resolve(name):
                missing.append(name)
        return missing
