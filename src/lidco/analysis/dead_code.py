"""Dead code detection — Task 339."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class DeadSymbol:
    name: str
    kind: str   # "function" | "class" | "variable" | "import"
    file: str
    line: int


_SKIP_NAMES = frozenset({
    "__all__", "__init__", "__main__", "__version__", "__author__",
    "__name__", "__file__", "__doc__", "__slots__", "__annotations__",
})


class DeadCodeDetector:
    """Find defined top-level symbols that are never referenced in the same file.

    Limitations
    -----------
    - Single-file analysis only; cross-module usage is not detected.
    - Names starting with ``_`` are excluded (conventionally private/unused-ok).
    - ``from x import *`` disables analysis for that file (returns empty).
    """

    def scan_file(self, source: str, file_path: str = "") -> list[DeadSymbol]:
        """Scan *source* for top-level symbols that appear to be unused."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        # Bail out if there's a star-import (analysis is unreliable)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        return []

        defined: dict[str, tuple[str, int]] = {}  # name -> (kind, line)

        for node in ast.iter_child_nodes(tree):
            # Functions and async functions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if not name.startswith("_") and name not in _SKIP_NAMES:
                    defined[name] = ("function", node.lineno)

            # Classes
            elif isinstance(node, ast.ClassDef):
                name = node.name
                if not name.startswith("_") and name not in _SKIP_NAMES:
                    defined[name] = ("class", node.lineno)

            # Simple assignments: X = ...  or  X: type = ...
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        n = target.id
                        if (
                            not n.startswith("_")
                            and n not in _SKIP_NAMES
                            and not n.isupper()  # skip ALL_CAPS constants
                        ):
                            defined[n] = ("variable", node.lineno)

            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    n = node.target.id
                    if (
                        not n.startswith("_")
                        and n not in _SKIP_NAMES
                        and not n.isupper()
                    ):
                        defined[n] = ("variable", node.lineno)

            # Imports
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name.split(".")[0]
                    if not name.startswith("_") and name not in _SKIP_NAMES:
                        defined[name] = ("import", node.lineno)

            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    if not name.startswith("_") and name not in _SKIP_NAMES:
                        defined[name] = ("import", node.lineno)

        if not defined:
            return []

        # Collect all Name references outside definition sites
        used: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            # Also catch attribute access on the defined names
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used.add(node.value.id)

        # Any symbol in __all__ is considered used
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(
                                    elt.value, str
                                ):
                                    used.add(elt.value)

        dead: list[DeadSymbol] = []
        for name, (kind, line) in defined.items():
            # Count Name nodes with Load context — these are actual uses.
            # FunctionDef/ClassDef definitions don't produce Load Name nodes,
            # so any Load occurrence is a real reference.
            load_occurrences = sum(
                1
                for n in ast.walk(tree)
                if (
                    isinstance(n, ast.Name)
                    and n.id == name
                    and isinstance(n.ctx, ast.Load)
                )
            )
            if load_occurrences == 0:
                dead.append(
                    DeadSymbol(name=name, kind=kind, file=file_path, line=line)
                )

        return dead
