"""Dead code elimination — Q134 task 805."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import List


@dataclass
class EliminationResult:
    removed_names: List[str] = field(default_factory=list)
    removed_lines: int = 0
    new_source: str = ""


class DeadCodeEliminator:
    """Remove unreachable code and unused imports."""

    def eliminate(self, source: str) -> EliminationResult:
        """Remove unreachable code after return/raise and unused imports."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return EliminationResult(new_source=source)

        dead_regions = self.find_dead_code(source)
        if not dead_regions:
            return EliminationResult(new_source=source)

        lines = source.splitlines(True)
        removed_names: list[str] = []
        lines_to_remove: set[int] = set()

        for region in dead_regions:
            rtype = region.get("type", "")
            line = region.get("line", 0)
            end_line = region.get("end_line", line)
            name = region.get("name", "")

            for ln in range(line, end_line + 1):
                lines_to_remove.add(ln)
            if name and name not in removed_names:
                removed_names.append(name)

        new_lines = [
            l for i, l in enumerate(lines, 1) if i not in lines_to_remove
        ]
        new_source = "".join(new_lines)

        return EliminationResult(
            removed_names=removed_names,
            removed_lines=len(lines_to_remove),
            new_source=new_source,
        )

    def find_dead_code(self, source: str) -> List[dict]:
        """List dead regions: unreachable code after return/raise, unused imports."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        regions: list[dict] = []

        # 1. Unreachable code after return/raise/break/continue
        self._find_unreachable(tree, regions)

        # 2. Unused imports
        self._find_unused_imports(tree, source, regions)

        return regions

    def remove_unused_imports(self, source: str) -> EliminationResult:
        """Remove only unused imports."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return EliminationResult(new_source=source)

        regions: list[dict] = []
        self._find_unused_imports(tree, source, regions)

        if not regions:
            return EliminationResult(new_source=source)

        lines = source.splitlines(True)
        removed_names: list[str] = []
        lines_to_remove: set[int] = set()

        for region in regions:
            line = region.get("line", 0)
            end_line = region.get("end_line", line)
            name = region.get("name", "")
            for ln in range(line, end_line + 1):
                lines_to_remove.add(ln)
            if name and name not in removed_names:
                removed_names.append(name)

        new_lines = [
            l for i, l in enumerate(lines, 1) if i not in lines_to_remove
        ]
        new_source = "".join(new_lines)

        return EliminationResult(
            removed_names=removed_names,
            removed_lines=len(lines_to_remove),
            new_source=new_source,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_unreachable(self, tree: ast.AST, regions: list[dict]) -> None:
        """Find statements after return/raise/break/continue in function bodies."""
        for node in ast.walk(tree):
            body: list[ast.stmt] | None = None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
            elif isinstance(node, (ast.For, ast.While)):
                body = node.body
            elif isinstance(node, (ast.If,)):
                body = node.body
                # Also check orelse
                self._check_body_for_unreachable(node.orelse, regions)

            if body is not None:
                self._check_body_for_unreachable(body, regions)

    def _check_body_for_unreachable(
        self, body: list[ast.stmt], regions: list[dict]
    ) -> None:
        terminal_types = (ast.Return, ast.Raise, ast.Break, ast.Continue)
        found_terminal = False
        for stmt in body:
            if found_terminal:
                end_line = getattr(stmt, "end_lineno", stmt.lineno) or stmt.lineno
                name = ""
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = stmt.name
                elif isinstance(stmt, ast.ClassDef):
                    name = stmt.name
                elif isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            name = t.id
                            break
                regions.append(
                    {
                        "type": "unreachable",
                        "line": stmt.lineno,
                        "end_line": end_line,
                        "name": name,
                    }
                )
            if isinstance(stmt, terminal_types):
                found_terminal = True

    def _find_unused_imports(
        self, tree: ast.AST, source: str, regions: list[dict]
    ) -> None:
        """Detect import names not referenced elsewhere in the module."""
        # Collect all imported names and their line info
        imported: list[tuple[str, int, int]] = []  # (name, line, end_line)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    end_line = getattr(node, "end_lineno", node.lineno) or node.lineno
                    imported.append((name, node.lineno, end_line))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    end_line = getattr(node, "end_lineno", node.lineno) or node.lineno
                    imported.append((name, node.lineno, end_line))

        if not imported:
            return

        # Collect all Name references (Load context) that are NOT part of imports
        import_lines: set[int] = set()
        for _, line, end_line in imported:
            for ln in range(line, end_line + 1):
                import_lines.add(ln)

        used_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.lineno not in import_lines:
                    used_names.add(node.id)
            # Attribute access: e.g., os.path -> "os" is used
            if isinstance(node, ast.Attribute):
                val = node.value
                while isinstance(val, ast.Attribute):
                    val = val.value
                if isinstance(val, ast.Name) and val.lineno not in import_lines:
                    used_names.add(val.id)

        # Also check string references (decorators, type annotations as strings, etc.)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for imp_name, _, _ in imported:
                    if imp_name in node.value:
                        used_names.add(imp_name)

        for imp_name, line, end_line in imported:
            if imp_name not in used_names:
                regions.append(
                    {
                        "type": "unused_import",
                        "line": line,
                        "end_line": end_line,
                        "name": imp_name,
                    }
                )
