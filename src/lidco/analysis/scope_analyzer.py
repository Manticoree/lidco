"""Scope analysis for Python source — Q125."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Scope:
    name: str
    kind: str  # "module"/"class"/"function"
    parent: Optional[str]  # parent scope name
    symbols: list[str] = field(default_factory=list)
    line: int = 0


class ScopeAnalyzer:
    """Build a flat list of scopes from Python source."""

    def analyze(self, source: str, module_name: str = "<module>") -> list[Scope]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        scopes: list[Scope] = []

        # Module scope is always first
        module_scope = Scope(
            name=module_name,
            kind="module",
            parent=None,
            line=0,
        )
        # Collect top-level names
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                module_scope.symbols.append(node.name)
            elif isinstance(node, ast.ClassDef):
                module_scope.symbols.append(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        module_scope.symbols.append(t.id)
        scopes.append(module_scope)

        # Walk for class and function scopes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                sym: list[str] = []
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        sym.append(child.name)
                    elif isinstance(child, ast.Assign):
                        for t in child.targets:
                            if isinstance(t, ast.Name):
                                sym.append(t.id)
                scopes.append(
                    Scope(
                        name=node.name,
                        kind="class",
                        parent=module_name,
                        symbols=sym,
                        line=node.lineno,
                    )
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sym = []
                for child in ast.walk(node):
                    if child is node:
                        continue
                    if isinstance(child, ast.Name) and isinstance(
                        child.ctx, ast.Store
                    ):
                        if child.id not in sym:
                            sym.append(child.id)
                # Add args
                for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                    if arg.arg not in sym:
                        sym.append(arg.arg)
                scopes.append(
                    Scope(
                        name=node.name,
                        kind="function",
                        parent=module_name,
                        symbols=sym,
                        line=node.lineno,
                    )
                )

        return scopes

    def find_scope(self, name: str, scopes: list[Scope]) -> Optional[Scope]:
        for s in scopes:
            if s.name == name:
                return s
        return None

    def children(self, name: str, scopes: list[Scope]) -> list[Scope]:
        return [s for s in scopes if s.parent == name]
