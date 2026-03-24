"""Symbol-aware code navigation — find definitions, references, callers (Sourcegraph Cody parity)."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SymbolLocation:
    file: str
    line: int
    column: int
    kind: str          # "def" | "class" | "call" | "import" | "assign"
    context: str       # the full line


@dataclass
class NavigationResult:
    symbol: str
    definitions: list[SymbolLocation]
    references: list[SymbolLocation]
    total: int

    def format_summary(self) -> str:
        lines = [f"Symbol: {self.symbol} — {len(self.definitions)} def(s), {len(self.references)} ref(s)"]
        for d in self.definitions[:5]:
            lines.append(f"  DEF  {d.file}:{d.line}  {d.context.strip()[:60]}")
        for r in self.references[:10]:
            lines.append(f"  REF  {r.file}:{r.line}  {r.context.strip()[:60]}")
        return "\n".join(lines)


_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "dist", "build"}


class CodeNavigator:
    """Find symbol definitions, references, and callers across a Python codebase."""

    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()

    def _iter_py_files(self) -> list[Path]:
        result: list[Path] = []
        for p in self.root.rglob("*.py"):
            if not any(part in _SKIP_DIRS for part in p.parts):
                result.append(p)
        return result

    def find(self, symbol: str) -> NavigationResult:
        """Find all definitions and references for a symbol."""
        defs: list[SymbolLocation] = []
        refs: list[SymbolLocation] = []
        def_pattern = re.compile(
            r"^\s*(?:def|async\s+def|class)\s+" + re.escape(symbol) + r"\b"
        )
        ref_pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
        assign_pattern = re.compile(r"^\s*" + re.escape(symbol) + r"\s*=")

        for path in self._iter_py_files():
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                if def_pattern.match(line):
                    defs.append(SymbolLocation(
                        file=str(path), line=lineno, column=line.index(symbol),
                        kind="def", context=line,
                    ))
                elif assign_pattern.match(line):
                    defs.append(SymbolLocation(
                        file=str(path), line=lineno, column=0,
                        kind="assign", context=line,
                    ))
                elif ref_pattern.search(line) and not def_pattern.match(line) and not assign_pattern.match(line):
                    refs.append(SymbolLocation(
                        file=str(path), line=lineno, column=line.find(symbol),
                        kind="call", context=line,
                    ))

        return NavigationResult(symbol=symbol, definitions=defs, references=refs, total=len(defs) + len(refs))

    def callers(self, func_name: str) -> list[SymbolLocation]:
        """Return all call sites for a function (lines containing func_name followed by '(')."""
        pattern = re.compile(r"\b" + re.escape(func_name) + r"\s*\(")
        result: list[SymbolLocation] = []
        for path in self._iter_py_files():
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                if pattern.search(line):
                    result.append(SymbolLocation(
                        file=str(path), line=lineno, column=line.find(func_name),
                        kind="call", context=line,
                    ))
        return result

    def symbols_in_file(self, file_path: str) -> list[SymbolLocation]:
        """Return all top-level definitions in a file."""
        p = Path(file_path)
        if not p.exists():
            return []
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            return []
        result: list[SymbolLocation] = []
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                lineno = node.lineno
                ctx = lines[lineno - 1] if lineno <= len(lines) else ""
                kind = "class" if isinstance(node, ast.ClassDef) else "def"
                result.append(SymbolLocation(
                    file=str(p), line=lineno, column=node.col_offset,
                    kind=kind, context=ctx,
                ))
        return result
