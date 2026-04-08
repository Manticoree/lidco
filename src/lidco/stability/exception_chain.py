"""
Exception Chain Analyzer.

Traces exception propagation paths, finds unhandled raises, audits catch-all
patterns, and checks raise...from chaining completeness.
"""
from __future__ import annotations

import ast
import textwrap


class ExceptionChainAnalyzer:
    """Analyzes exception propagation and handling patterns in Python source."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def trace_propagation(self, source_code: str) -> list[dict]:
        """Trace exception propagation paths through try/except/raise chains.

        Returns dicts with: line, exception_type, action, handler_line.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                # Record each handler
                for handler in node.handlers:
                    handler_line = handler.lineno
                    exc_type = "Exception"
                    if handler.type is not None:
                        exc_type = ast.unparse(handler.type)

                    # Record caught
                    results.append({
                        "line": handler_line,
                        "exception_type": exc_type,
                        "action": "caught",
                        "handler_line": handler_line,
                    })

                    # Look for raise statements inside handler body
                    for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
                        if isinstance(child, ast.Raise):
                            raise_line = child.lineno
                            if child.exc is None:
                                # bare re-raise
                                results.append({
                                    "line": raise_line,
                                    "exception_type": exc_type,
                                    "action": "reraised",
                                    "handler_line": handler_line,
                                })
                            else:
                                raised_type = ast.unparse(child.exc) if child.exc else exc_type
                                results.append({
                                    "line": raise_line,
                                    "exception_type": raised_type,
                                    "action": "raised",
                                    "handler_line": handler_line,
                                })

        return results

    def find_unhandled(self, source_code: str) -> list[dict]:
        """Find raise statements not inside any try block.

        Returns dicts with: line, exception_type, context.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        # Collect all line ranges covered by try blocks
        try_ranges: list[tuple[int, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                start = node.lineno
                end = node.end_lineno or node.lineno
                try_ranges.append((start, end))

        def _in_try(line: int) -> bool:
            return any(s <= line <= e for s, e in try_ranges)

        for node in ast.walk(tree):
            if isinstance(node, ast.Raise):
                line = node.lineno
                if not _in_try(line):
                    exc_type = "unknown"
                    if node.exc is not None:
                        exc_type = ast.unparse(node.exc)
                    # Determine context: enclosing function name
                    context = _enclosing_function(tree, line)
                    results.append({
                        "line": line,
                        "exception_type": exc_type,
                        "context": context,
                    })

        return results

    def audit_catch_all(self, source_code: str) -> list[dict]:
        """Find bare except: or except Exception: that swallow errors.

        Returns dicts with: line, pattern, severity, suggestion.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    line = handler.lineno
                    if handler.type is None:
                        # bare except:
                        results.append({
                            "line": line,
                            "pattern": "bare except",
                            "severity": "HIGH",
                            "suggestion": (
                                "Replace bare 'except:' with a specific exception type "
                                "or at minimum 'except Exception as e:' and re-raise or log."
                            ),
                        })
                    elif isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
                        # Check if body just passes or swallows silently
                        body_nodes = [n for n in handler.body if not isinstance(n, ast.Pass)]
                        has_raise = any(
                            isinstance(n, ast.Raise) for n in ast.walk(
                                ast.Module(body=handler.body, type_ignores=[])
                            )
                        )
                        has_log = any(
                            isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                            and _call_name(n.value) in ("log", "logging", "logger", "print")
                            for n in ast.walk(ast.Module(body=handler.body, type_ignores=[]))
                        )
                        if not has_raise and not has_log:
                            results.append({
                                "line": line,
                                "pattern": "except Exception (swallowed)",
                                "severity": "MEDIUM",
                                "suggestion": (
                                    "Catching 'Exception' without re-raising or logging "
                                    "hides errors. Add logging or re-raise the exception."
                                ),
                            })

        return results

    def check_chain_completeness(self, source_code: str) -> list[dict]:
        """Verify raise ... from ... is used for exception chaining.

        Returns dicts with: line, has_from, suggestion.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        # Find raises inside except handlers — these should use `from`
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
                        if isinstance(child, ast.Raise) and child.exc is not None:
                            has_from = child.cause is not None
                            suggestion = ""
                            if not has_from:
                                suggestion = (
                                    "Use 'raise NewException(...) from original_exc' to "
                                    "preserve the exception chain context."
                                )
                            results.append({
                                "line": child.lineno,
                                "has_from": has_from,
                                "suggestion": suggestion,
                            })

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_name(call_node: ast.Call) -> str:
    """Return the base name of a call node (best-effort)."""
    if isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    return ""


def _enclosing_function(tree: ast.AST, target_line: int) -> str:
    """Return the name of the innermost function containing target_line."""
    best: str = "<module>"
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = node.end_lineno or node.lineno
            if start <= target_line <= end:
                best = node.name
    return best
