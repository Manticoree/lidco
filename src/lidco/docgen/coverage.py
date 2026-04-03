"""Documentation Coverage Analyzer — measure and report docstring coverage (stdlib only).

Parses Python source with ``ast`` to find functions and classes, checks which
have docstrings, detects undocumented parameters, and identifies stale docs
where the implementation changed but the docstring was not updated.
"""
from __future__ import annotations

import ast
import difflib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CoverageResult:
    """Result of a documentation coverage analysis."""

    total_symbols: int
    documented: int
    undocumented: list[str]
    coverage_pct: float


class DocCoverageAnalyzer:
    """Analyze documentation coverage in Python source code."""

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def analyze(self, source: str) -> CoverageResult:
        """Find functions/classes and check for docstrings.

        Returns a *CoverageResult* with totals and a list of undocumented
        symbol names.
        """
        tree = _parse(source)
        symbols: list[tuple[str, bool]] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append((node.name, _has_docstring(node)))
            elif isinstance(node, ast.ClassDef):
                symbols.append((node.name, _has_docstring(node)))

        total = len(symbols)
        documented = sum(1 for _, has_doc in symbols if has_doc)
        undocumented = [name for name, has_doc in symbols if not has_doc]
        pct = (documented / total * 100.0) if total else 100.0
        return CoverageResult(
            total_symbols=total,
            documented=documented,
            undocumented=undocumented,
            coverage_pct=round(pct, 1),
        )

    def find_missing_params(self, source: str) -> list[dict]:
        """Return functions whose parameters are not documented in the docstring.

        Each entry is a dict with keys ``name`` and ``missing``.
        """
        tree = _parse(source)
        results: list[dict] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = _get_docstring(node)
            if not doc:
                continue
            params = _param_names(node)
            missing = [p for p in params if p not in doc]
            if missing:
                results.append({"name": node.name, "missing": missing})
        return results

    def find_stale(self, source: str, old_source: str) -> list[str]:
        """Identify functions whose body changed but whose docstring did not.

        Compares *source* (new) against *old_source* (previous version) and
        returns a list of function names with potentially stale docs.
        """
        new_funcs = _function_map(_parse(source), source)
        old_funcs = _function_map(_parse(old_source), old_source)

        stale: list[str] = []
        for name, (new_doc, new_body) in new_funcs.items():
            if name not in old_funcs:
                continue
            old_doc, old_body = old_funcs[name]
            body_changed = new_body != old_body
            doc_same = new_doc == old_doc
            if body_changed and doc_same and new_doc:
                stale.append(name)
        return stale

    def summary(self, result: CoverageResult) -> str:
        """Human-readable summary of a *CoverageResult*."""
        lines = [
            f"Coverage: {result.coverage_pct}% ({result.documented}/{result.total_symbols} documented)",
        ]
        if result.undocumented:
            lines.append("Undocumented: " + ", ".join(result.undocumented))
        return "\n".join(lines)


# ------------------------------------------------------------------ #
# Internal helpers                                                     #
# ------------------------------------------------------------------ #


def _parse(source: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"Syntax error: {exc}") from exc


def _has_docstring(node: ast.AST) -> bool:
    body = getattr(node, "body", [])
    if not body:
        return False
    first = body[0]
    return (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )


def _get_docstring(node: ast.AST) -> str:
    body = getattr(node, "body", [])
    if not body:
        return ""
    first = body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return first.value.value
    return ""


def _param_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    return [
        a.arg for a in node.args.args if a.arg not in ("self", "cls")
    ]


def _function_map(
    tree: ast.Module, source: str
) -> dict[str, tuple[str, str]]:
    """Return {name: (docstring, body_source)} for all functions."""
    lines = source.splitlines()
    result: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = _get_docstring(node)
        # body source: lines from first statement after docstring to end
        start = node.body[0].end_lineno if _has_docstring(node) and len(node.body) > 1 else node.lineno
        end = node.end_lineno or node.lineno
        body_text = "\n".join(lines[start:end])
        result[node.name] = (doc, body_text)
    return result
