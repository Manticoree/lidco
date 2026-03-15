"""Symbol index for cross-file lookup — Task 344."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SymbolDef:
    name: str
    kind: str    # "function" | "class" | "method" | "variable" | "import"
    file: str
    line: int
    qualified: str  # e.g. "MyClass.method"


@dataclass
class SymbolIndex:
    """Index of all symbols across a set of files."""

    _defs: list[SymbolDef] = field(default_factory=list)

    def add(self, sym: SymbolDef) -> None:
        self._defs.append(sym)

    def find(self, name: str) -> list[SymbolDef]:
        """Find all definitions matching *name* (simple or qualified)."""
        return [s for s in self._defs if s.name == name or s.qualified == name]

    def find_by_kind(self, kind: str) -> list[SymbolDef]:
        return [s for s in self._defs if s.kind == kind]

    def find_in_file(self, file: str) -> list[SymbolDef]:
        return [s for s in self._defs if s.file == file]

    def all_names(self) -> set[str]:
        return {s.name for s in self._defs}

    def __len__(self) -> int:
        return len(self._defs)


class SymbolIndexBuilder:
    """Build a SymbolIndex from Python source files."""

    def build(self, sources: dict[str, str]) -> SymbolIndex:
        """Build index from ``{file_path: source_code}`` mapping."""
        index = SymbolIndex()
        for file_path, source in sources.items():
            self._index_file(source, file_path, index)
        return index

    def _index_file(
        self, source: str, file_path: str, index: SymbolIndex
    ) -> None:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                index.add(
                    SymbolDef(
                        name=node.name,
                        kind="function",
                        file=file_path,
                        line=node.lineno,
                        qualified=node.name,
                    )
                )

            elif isinstance(node, ast.ClassDef):
                index.add(
                    SymbolDef(
                        name=node.name,
                        kind="class",
                        file=file_path,
                        line=node.lineno,
                        qualified=node.name,
                    )
                )
                # Index methods
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        index.add(
                            SymbolDef(
                                name=child.name,
                                kind="method",
                                file=file_path,
                                line=child.lineno,
                                qualified=f"{node.name}.{child.name}",
                            )
                        )

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        index.add(
                            SymbolDef(
                                name=target.id,
                                kind="variable",
                                file=file_path,
                                line=node.lineno,
                                qualified=target.id,
                            )
                        )

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    index.add(
                        SymbolDef(
                            name=name,
                            kind="import",
                            file=file_path,
                            line=node.lineno,
                            qualified=name,
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    index.add(
                        SymbolDef(
                            name=name,
                            kind="import",
                            file=file_path,
                            line=node.lineno,
                            qualified=name,
                        )
                    )
