"""Refactoring opportunity detection — Task 341."""

from __future__ import annotations

import ast
import enum
from dataclasses import dataclass


class RefactorKind(enum.Enum):
    LONG_FUNCTION = "long_function"
    DEEP_NESTING = "deep_nesting"
    TOO_MANY_ARGS = "too_many_args"
    MAGIC_NUMBER = "magic_number"


@dataclass(frozen=True)
class RefactorCandidate:
    kind: RefactorKind
    file: str
    line: int
    name: str
    detail: str


# Integer values that are NOT considered magic numbers
_ALLOWED_INTS = frozenset({0, 1, -1, 2})

_NESTING_NODES = (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While,
                  ast.With, ast.AsyncWith, ast.Try, ast.ExceptHandler)


class RefactorScanner:
    """Scan Python source for common refactoring opportunities."""

    def scan(self, source: str, file_path: str = "") -> list[RefactorCandidate]:
        """Return a list of RefactorCandidate items found in *source*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        results: list[RefactorCandidate] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_long(node, file_path, results)
                self._check_args(node, file_path, results)
                self._check_nesting(node, file_path, results)
                self._check_magic_numbers(node, file_path, results)
        return results

    # ------------------------------------------------------------------ #
    # Checks                                                               #
    # ------------------------------------------------------------------ #

    def _check_long(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        results: list[RefactorCandidate],
    ) -> None:
        end = getattr(node, "end_lineno", node.lineno)
        length = end - node.lineno + 1
        if length > 50:
            results.append(
                RefactorCandidate(
                    kind=RefactorKind.LONG_FUNCTION,
                    file=file_path,
                    line=node.lineno,
                    name=node.name,
                    detail=f"{length} lines (threshold: 50)",
                )
            )

    def _check_args(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        results: list[RefactorCandidate],
    ) -> None:
        args = node.args
        all_args = (
            list(args.posonlyargs)
            + list(args.args)
            + list(args.kwonlyargs)
        )
        # Exclude self/cls
        if all_args and all_args[0].arg in ("self", "cls"):
            all_args = all_args[1:]
        if args.vararg:
            all_args.append(args.vararg)
        if args.kwarg:
            all_args.append(args.kwarg)

        count = len(all_args)
        if count > 5:
            results.append(
                RefactorCandidate(
                    kind=RefactorKind.TOO_MANY_ARGS,
                    file=file_path,
                    line=node.lineno,
                    name=node.name,
                    detail=f"{count} parameters (threshold: 5)",
                )
            )

    def _check_nesting(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        results: list[RefactorCandidate],
    ) -> None:
        max_depth = [0]

        def _walk(subtree: ast.AST, depth: int) -> None:
            if depth > max_depth[0]:
                max_depth[0] = depth
            for child in ast.iter_child_nodes(subtree):
                if isinstance(child, _NESTING_NODES):
                    _walk(child, depth + 1)
                else:
                    _walk(child, depth)

        _walk(node, 0)
        if max_depth[0] > 4:
            results.append(
                RefactorCandidate(
                    kind=RefactorKind.DEEP_NESTING,
                    file=file_path,
                    line=node.lineno,
                    name=node.name,
                    detail=f"max nesting depth {max_depth[0]} (threshold: 4)",
                )
            )

    def _check_magic_numbers(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        results: list[RefactorCandidate],
    ) -> None:
        """Flag integer literals not in {0, 1, -1, 2} inside function bodies.

        Excluded:
        - Simple assignment RHS (``x = 42``)
        - Default parameter values
        - ``-1`` / ``+1`` unary variants (handled via _ALLOWED_INTS)
        """
        # Collect positions that are assignment RHS targets (not magic)
        assignment_value_ids: set[int] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                assignment_value_ids.add(id(child.value))
            elif isinstance(child, ast.AnnAssign) and child.value is not None:
                assignment_value_ids.add(id(child.value))

        # Default param values are not magic
        default_ids: set[int] = set()
        for d in node.args.defaults + node.args.kw_defaults:
            if d is not None:
                default_ids.add(id(d))

        found_magic = False
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, int):
                val = child.value
                if val in _ALLOWED_INTS:
                    continue
                if id(child) in assignment_value_ids or id(child) in default_ids:
                    continue
                found_magic = True
                break

        if found_magic:
            results.append(
                RefactorCandidate(
                    kind=RefactorKind.MAGIC_NUMBER,
                    file=file_path,
                    line=node.lineno,
                    name=node.name,
                    detail="contains magic number literals",
                )
            )
