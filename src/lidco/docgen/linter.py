"""Documentation Linter — lint docstrings for style, accuracy, and deprecation (stdlib only).

Uses ``ast`` to parse Python source and validates docstring content against
function signatures, style conventions, and deprecation annotations.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LintIssue:
    """A single documentation lint issue."""

    line: int
    message: str
    severity: str  # "error", "warning", "info"
    rule: str


class DocLinter:
    """Lint Python docstrings for correctness and style."""

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def lint(self, source: str) -> list[LintIssue]:
        """Run all lint checks on *source* and return issues."""
        issues: list[LintIssue] = []
        issues.extend(self._check_missing(source))
        issues.extend(self.check_param_mismatch(source))
        return sorted(issues, key=lambda i: i.line)

    def check_param_mismatch(self, source: str) -> list[LintIssue]:
        """Check that documented parameters match the actual signature."""
        tree = _parse(source)
        issues: list[LintIssue] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = _get_docstring(node)
            if not doc:
                continue

            actual_params = {
                a.arg for a in node.args.args if a.arg not in ("self", "cls")
            }
            documented_params = _extract_doc_params(doc)

            for p in actual_params - documented_params:
                issues.append(LintIssue(
                    line=node.lineno,
                    message=f"Parameter '{p}' not documented in {node.name}",
                    severity="warning",
                    rule="param-missing",
                ))
            for p in documented_params - actual_params:
                issues.append(LintIssue(
                    line=node.lineno,
                    message=f"Documented parameter '{p}' not in signature of {node.name}",
                    severity="error",
                    rule="param-extra",
                ))
        return issues

    def check_style(self, docstring: str) -> list[LintIssue]:
        """Check docstring style conventions (Google / numpy / sphinx)."""
        issues: list[LintIssue] = []

        if not docstring.strip():
            issues.append(LintIssue(
                line=0, message="Empty docstring", severity="warning", rule="style-empty",
            ))
            return issues

        lines = docstring.strip().splitlines()
        first = lines[0].strip()

        # Should start with a capital letter
        if first and first[0].islower():
            issues.append(LintIssue(
                line=0,
                message="Docstring should start with a capital letter",
                severity="info",
                rule="style-capitalization",
            ))

        # Should end with a period
        summary_line = first.rstrip()
        if summary_line and not summary_line.endswith((".","!","?")):
            issues.append(LintIssue(
                line=0,
                message="Summary line should end with punctuation",
                severity="info",
                rule="style-punctuation",
            ))

        # Multi-line: second line should be blank
        if len(lines) > 1 and lines[1].strip():
            issues.append(LintIssue(
                line=0,
                message="Second line of multi-line docstring should be blank",
                severity="info",
                rule="style-blank-line",
            ))

        return issues

    def check_deprecated(self, source: str, deprecated: set[str]) -> list[LintIssue]:
        """Check that deprecated symbols have deprecation notices in their docstrings."""
        tree = _parse(source)
        issues: list[LintIssue] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name not in deprecated:
                continue
            doc = _get_docstring(node)
            if not doc or "deprecated" not in doc.lower():
                issues.append(LintIssue(
                    line=node.lineno,
                    message=f"'{node.name}' is deprecated but lacks deprecation notice in docstring",
                    severity="error",
                    rule="deprecated-undocumented",
                ))
        return issues

    def summary(self, issues: list[LintIssue]) -> str:
        """Human-readable summary of lint issues."""
        if not issues:
            return "No documentation lint issues found."
        counts: dict[str, int] = {}
        for issue in issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        parts = [f"{len(issues)} issue(s) found:"]
        for sev in ("error", "warning", "info"):
            if sev in counts:
                parts.append(f"  {sev}: {counts[sev]}")
        return "\n".join(parts)

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _check_missing(self, source: str) -> list[LintIssue]:
        tree = _parse(source)
        issues: list[LintIssue] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not _has_docstring(node) and not node.name.startswith("_"):
                    issues.append(LintIssue(
                        line=node.lineno,
                        message=f"Public function '{node.name}' has no docstring",
                        severity="warning",
                        rule="missing-docstring",
                    ))
            elif isinstance(node, ast.ClassDef):
                if not _has_docstring(node) and not node.name.startswith("_"):
                    issues.append(LintIssue(
                        line=node.lineno,
                        message=f"Public class '{node.name}' has no docstring",
                        severity="warning",
                        rule="missing-docstring",
                    ))
        return issues


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


def _extract_doc_params(doc: str) -> set[str]:
    """Extract parameter names from docstring (Google, numpy, sphinx styles)."""
    params: set[str] = set()
    # Google: "    name (type): ..." or "    name: ..."
    for m in re.finditer(r"^\s+(\w+)\s*(?:\([^)]*\))?\s*:", doc, re.MULTILINE):
        params.add(m.group(1))
    # Sphinx: ":param name:" or ":param type name:"
    for m in re.finditer(r":param\s+(?:\w+\s+)?(\w+)\s*:", doc):
        params.add(m.group(1))
    # numpy: "name : type"
    for m in re.finditer(r"^(\w+)\s*:\s*\w", doc, re.MULTILINE):
        params.add(m.group(1))
    # Remove common section headers that get false-matched
    params -= {"Args", "Returns", "Raises", "Yields", "Notes", "Examples",
               "Parameters", "Attributes", "See", "References", "Todo"}
    return params
