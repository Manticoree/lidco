"""
Graceful Degradation Checker.

Verifies that optional features have fallbacks, optional dependency imports
are guarded correctly, network calls have timeouts/retry, and timeout
handling is correct.
"""
from __future__ import annotations

import ast
import re
import textwrap


class GracefulDegradationChecker:
    """Checks Python source for graceful degradation patterns."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_fallbacks(self, source_code: str) -> list[dict]:
        """Verify graceful fallbacks exist for optional features.

        Looks for try/except blocks where the except clause body is just
        `pass` or assigns a fallback value.

        Returns dicts with: line, feature, has_fallback, suggestion.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                exc_type = "Exception"
                if handler.type is not None:
                    exc_type = ast.unparse(handler.type)

                # Determine feature name from try body (best-effort: first call)
                feature = _first_call_name(node.body)
                body_stmts = handler.body

                # Has fallback: body contains assignment, return, or a non-trivial statement
                has_fallback = _has_meaningful_fallback(body_stmts)
                suggestion = ""
                if not has_fallback:
                    suggestion = (
                        f"Add a fallback for '{feature}' in the except {exc_type} block "
                        "(e.g., assign a default value or return a safe substitute)."
                    )

                results.append({
                    "line": handler.lineno,
                    "feature": feature,
                    "has_fallback": has_fallback,
                    "suggestion": suggestion,
                })

        return results

    def check_optional_deps(self, source_code: str) -> list[dict]:
        """Verify optional dependency imports have proper fallbacks.

        Looks for `try: import X / except ImportError: X = None` pattern.

        Returns dicts with: line, module, has_fallback, fallback_correct.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue

            # Collect imported module names in the try body
            imported: list[tuple[str, int]] = []
            for stmt in node.body:
                if isinstance(stmt, ast.Import):
                    for alias in stmt.names:
                        imported.append((alias.name, stmt.lineno))
                elif isinstance(stmt, ast.ImportFrom) and stmt.module:
                    imported.append((stmt.module, stmt.lineno))

            if not imported:
                continue

            # Check except ImportError handlers
            import_error_handlers = [
                h for h in node.handlers
                if h.type is not None and ast.unparse(h.type) in ("ImportError", "ModuleNotFoundError")
            ]
            bare_handlers = [h for h in node.handlers if h.type is None]
            relevant_handlers = import_error_handlers or bare_handlers

            for module, line in imported:
                has_fallback = bool(relevant_handlers)
                fallback_correct = False

                if has_fallback:
                    for handler in relevant_handlers:
                        # Correct: assigns module name to None
                        for stmt in handler.body:
                            if isinstance(stmt, ast.Assign):
                                for target in stmt.targets:
                                    target_name = ""
                                    if isinstance(target, ast.Name):
                                        target_name = target.id
                                    val = stmt.value
                                    is_none = isinstance(val, ast.Constant) and val.value is None
                                    short_name = module.split(".")[-1]
                                    if target_name in (module, short_name) and is_none:
                                        fallback_correct = True

                results.append({
                    "line": line,
                    "module": module,
                    "has_fallback": has_fallback,
                    "fallback_correct": fallback_correct,
                })

        return results

    def check_network_resilience(self, source_code: str) -> list[dict]:
        """Find network calls without timeout or retry.

        Returns dicts with: line, call, has_timeout, has_retry, suggestion.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        _NETWORK_FUNCS = {
            "get", "post", "put", "delete", "patch", "request",
            "urlopen", "urlretrieve", "fetch", "send", "connect",
        }

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = _get_call_name(node)
            if call_name not in _NETWORK_FUNCS:
                continue

            # Check for timeout keyword arg
            has_timeout = any(
                kw.arg == "timeout" for kw in node.keywords
            )
            # Check for retry: look at parent try block or decorators (heuristic)
            has_retry = _has_retry_context(tree, node.lineno)

            parts: list[str] = []
            if not has_timeout:
                parts.append("add timeout= parameter")
            if not has_retry:
                parts.append("add retry logic (e.g., tenacity or manual loop)")
            suggestion = "; ".join(parts) if parts else ""

            results.append({
                "line": node.lineno,
                "call": call_name,
                "has_timeout": has_timeout,
                "has_retry": has_retry,
                "suggestion": suggestion,
            })

        return results

    def check_timeout_behavior(self, source_code: str) -> list[dict]:
        """Verify timeout handling is correct.

        Returns dicts with: line, operation, timeout_value, suggestion.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg != "timeout":
                    continue
                op = _get_call_name(node)
                timeout_value: str = ast.unparse(kw.value)
                suggestion = ""
                # Warn about very large or zero timeouts
                try:
                    val = float(ast.literal_eval(kw.value))
                    if val <= 0:
                        suggestion = "Timeout value is <= 0 — this may disable the timeout entirely."
                    elif val > 300:
                        suggestion = "Timeout value is very large (>300s). Consider a shorter timeout."
                except (ValueError, TypeError):
                    pass  # dynamic value, skip

                results.append({
                    "line": node.lineno,
                    "operation": op,
                    "timeout_value": timeout_value,
                    "suggestion": suggestion,
                })

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_call_name(stmts: list[ast.stmt]) -> str:
    """Return the name of the first function call in a list of statements."""
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                name = _get_call_name(node)
                if name:
                    return name
    return "feature"


def _get_call_name(call: ast.Call) -> str:
    """Return best-effort name of a call."""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return ""


def _has_meaningful_fallback(stmts: list[ast.stmt]) -> bool:
    """Return True if the except body has something beyond pass."""
    for stmt in stmts:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            return True
        if isinstance(stmt, ast.Return):
            return True
        if isinstance(stmt, ast.Raise):
            return True
        if isinstance(stmt, ast.Expr):
            return True
    return False


def _has_retry_context(tree: ast.AST, target_line: int) -> bool:
    """Heuristic: check if there is a retry-related decorator or loop nearby."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = node.end_lineno or node.lineno
            if not (start <= target_line <= end):
                continue
            # Check decorators for retry
            for dec in node.decorator_list:
                dec_name = ast.unparse(dec).lower()
                if "retry" in dec_name or "retries" in dec_name:
                    return True
            # Check for while/for loop containing the line (manual retry loop)
            for child in ast.walk(node):
                if isinstance(child, (ast.While, ast.For)):
                    child_start = child.lineno
                    child_end = child.end_lineno or child.lineno
                    if child_start <= target_line <= child_end:
                        return True
    return False
