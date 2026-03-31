"""AST-based variable/parameter renaming — Q134 task 802."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class RenameResult:
    old_name: str
    new_name: str
    occurrences: int
    source: str


class VariableRenamer:
    """Rename variables and parameters in Python source using AST."""

    def rename(self, source: str, old_name: str, new_name: str) -> RenameResult:
        """AST-based rename of variables/params.  Returns *RenameResult*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return RenameResult(old_name=old_name, new_name=new_name, occurrences=0, source=source)

        occurrences = self._collect_name_nodes(tree, old_name)
        if not occurrences:
            return RenameResult(old_name=old_name, new_name=new_name, occurrences=0, source=source)

        # Also collect function/class def names and argument names
        lines = source.splitlines(True)
        # Build list of (line, col, length) replacements — process from end to start
        replacements: list[tuple[int, int, int]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == old_name:
                replacements.append((node.lineno, node.col_offset, len(old_name)))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == old_name:
                replacements.append((node.lineno, node.col_offset + len("def "), len(old_name)))
            elif isinstance(node, ast.ClassDef) and node.name == old_name:
                replacements.append((node.lineno, node.col_offset + len("class "), len(old_name)))
            elif isinstance(node, ast.arg) and node.arg == old_name:
                replacements.append((node.lineno, node.col_offset, len(old_name)))

        # Deduplicate and sort reverse for safe replacement
        replacements = sorted(set(replacements), key=lambda r: (r[0], r[1]), reverse=True)

        for lineno, col, length in replacements:
            idx = lineno - 1
            if 0 <= idx < len(lines):
                line = lines[idx]
                lines[idx] = line[:col] + new_name + line[col + length:]

        new_source = "".join(lines)
        return RenameResult(
            old_name=old_name,
            new_name=new_name,
            occurrences=len(replacements),
            source=new_source,
        )

    def find_occurrences(self, source: str, name: str) -> List[Tuple[int, int]]:
        """Return (line, col) positions where *name* appears as an AST Name/arg."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        positions: list[tuple[int, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == name:
                positions.append((node.lineno, node.col_offset))
            elif isinstance(node, ast.arg) and node.arg == name:
                positions.append((node.lineno, node.col_offset))
        return sorted(positions)

    def is_safe_rename(self, source: str, old_name: str, new_name: str) -> bool:
        """Check that *new_name* doesn't conflict with existing names."""
        if not new_name.isidentifier():
            return False
        if old_name == new_name:
            return False
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False

        existing_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                existing_names.add(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                existing_names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                existing_names.add(node.name)
            elif isinstance(node, ast.arg):
                existing_names.add(node.arg)
            elif isinstance(node, ast.alias):
                alias_name = node.asname if node.asname else node.name
                existing_names.add(alias_name)

        if old_name not in existing_names:
            return False
        if new_name in existing_names:
            return False
        return True

    # ------------------------------------------------------------------
    def _collect_name_nodes(self, tree: ast.AST, name: str) -> list[ast.AST]:
        nodes: list[ast.AST] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == name:
                nodes.append(node)
            elif isinstance(node, ast.arg) and node.arg == name:
                nodes.append(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                nodes.append(node)
            elif isinstance(node, ast.ClassDef) and node.name == name:
                nodes.append(node)
        return nodes
