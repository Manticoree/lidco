"""EditGraph — symbol relationship model for next-edit prediction context."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EditSite:
    file_path: str
    line: int
    relationship: str  # call_site | test | implementation | type_usage
    symbol: str = ""


class EditGraph:
    """In-memory symbol relationship graph for a project directory."""

    def __init__(self) -> None:
        # symbol -> list of EditSite
        self._graph: dict[str, list[EditSite]] = {}
        self._built = False

    @classmethod
    def build(cls, project_dir: Path) -> "EditGraph":
        """Scan Python files and build symbol reference graph."""
        g = cls()
        g._scan(project_dir)
        g._built = True
        return g

    def related_sites(self, symbol: str, file_path: str = "") -> list[EditSite]:
        """Return EditSite list for a symbol, excluding the definition file."""
        sites = self._graph.get(symbol, [])
        if file_path:
            sites = [s for s in sites if s.file_path != file_path]
        return sites

    def symbols(self) -> list[str]:
        return list(self._graph.keys())

    def _scan(self, project_dir: Path) -> None:
        for py_file in project_dir.rglob("*.py"):
            try:
                text = py_file.read_text(encoding="utf-8", errors="replace")
                rel_path = str(py_file.relative_to(project_dir))
                self._index_file(rel_path, text)
            except (OSError, ValueError):
                pass

    def _index_file(self, rel_path: str, text: str) -> None:
        lines = text.splitlines()
        is_test = "test_" in rel_path or rel_path.startswith("tests/")

        for i, line in enumerate(lines, 1):
            # Definitions
            def_match = re.match(r"^\s*(?:def|class)\s+(\w+)", line)
            if def_match:
                sym = def_match.group(1)
                rel = "test" if (is_test and sym.startswith("test_")) else "implementation"
                self._add(sym, EditSite(file_path=rel_path, line=i, relationship=rel, symbol=sym))
                # Also check for type annotations on definition lines (e.g. def f(x: T) -> T:)
                types = re.findall(r"(?::\s*|-> )([A-Z]\w+)", line)
                for sym in types:
                    self._add(sym, EditSite(file_path=rel_path, line=i, relationship="type_usage", symbol=sym))
                continue

            # Call sites: name(
            calls = re.findall(r"\b(\w+)\s*\(", line)
            for sym in calls:
                if len(sym) > 2 and not sym.startswith("_"):
                    self._add(sym, EditSite(file_path=rel_path, line=i, relationship="call_site", symbol=sym))

            # Type usage: : TypeName or -> TypeName
            types = re.findall(r"(?::\s*|-> )([A-Z]\w+)", line)
            for sym in types:
                self._add(sym, EditSite(file_path=rel_path, line=i, relationship="type_usage", symbol=sym))

    def _add(self, symbol: str, site: EditSite) -> None:
        if symbol not in self._graph:
            self._graph[symbol] = []
        self._graph[symbol].append(site)
