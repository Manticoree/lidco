"""
Recovery Path Validator.

Validates error recovery paths in try/except blocks, checks retry logic,
state restoration rollback, and data integrity patterns.
"""
from __future__ import annotations

import ast
import textwrap


class RecoveryPathValidator:
    """Validates recovery paths and resilience patterns in Python source."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_recovery(self, source_code: str) -> list[dict]:
        """Validate error recovery paths in try/except blocks.

        Returns dicts with: line, recovery_type, valid (bool), issues (list).
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
                issues: list[str] = []
                recovery_type = "unknown"
                body = handler.body

                # Bare pass — no recovery at all
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    recovery_type = "silent_ignore"
                    issues.append("Exception silently ignored (pass only)")
                # Has logging
                elif _has_logging(body):
                    recovery_type = "logged"
                # Has re-raise
                elif _has_reraise(body):
                    recovery_type = "reraised"
                # Has return with fallback value
                elif _has_return(body):
                    recovery_type = "fallback_return"
                # Has assignment (default value)
                elif _has_assignment(body):
                    recovery_type = "default_assignment"
                else:
                    recovery_type = "other"

                # Issues: no logging, no re-raise, and not a simple fallback
                if recovery_type == "silent_ignore":
                    issues.append("No logging or re-raise")
                if recovery_type == "other" and not issues:
                    # Body has something but it's unclear
                    pass

                valid = len(issues) == 0

                results.append({
                    "line": handler.lineno,
                    "recovery_type": recovery_type,
                    "valid": valid,
                    "issues": issues,
                })

        return results

    def check_retry_logic(self, source_code: str) -> list[dict]:
        """Verify retry logic is correct (has max retries, backoff, etc.).

        Returns dicts with: line, pattern, has_max_retries, has_backoff, suggestion.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        for node in ast.walk(tree):
            if not isinstance(node, (ast.While, ast.For)):
                continue

            # Heuristic: check if this looks like a retry loop
            source_slice = ast.unparse(node)
            lower_slice = source_slice.lower()
            if not any(k in lower_slice for k in ("retry", "retries", "attempt", "max_")):
                continue

            has_max_retries = _loop_has_max_retries(node)
            has_backoff = "sleep" in lower_slice or "backoff" in lower_slice or "wait" in lower_slice

            parts: list[str] = []
            if not has_max_retries:
                parts.append("add a max_retries limit to prevent infinite loops")
            if not has_backoff:
                parts.append("add backoff (time.sleep or exponential delay) between retries")
            suggestion = "; ".join(parts) if parts else ""

            results.append({
                "line": node.lineno,
                "pattern": "retry_loop",
                "has_max_retries": has_max_retries,
                "has_backoff": has_backoff,
                "suggestion": suggestion,
            })

        return results

    def check_state_restoration(self, source_code: str) -> list[dict]:
        """Find state modifications in try blocks and verify rollback in except.

        Returns dicts with: line, state_change, has_rollback, suggestion.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue

            # Collect attribute mutations in the try body
            mutations: list[tuple[int, str]] = _collect_mutations(node.body)
            if not mutations:
                continue

            # Check if any except handler restores state
            has_rollback = _handlers_have_rollback(node.handlers)

            for mut_line, mut_desc in mutations:
                suggestion = ""
                if not has_rollback:
                    suggestion = (
                        f"State change '{mut_desc}' in try block should be rolled back "
                        "in except handler to maintain consistency."
                    )
                results.append({
                    "line": mut_line,
                    "state_change": mut_desc,
                    "has_rollback": has_rollback,
                    "suggestion": suggestion,
                })

        return results

    def check_data_integrity(self, source_code: str) -> list[dict]:
        """Verify data operations have integrity checks (transactions, atomic writes).

        Returns dicts with: line, operation, has_integrity_check, suggestion.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        _DATA_OPS = {"write", "save", "commit", "insert", "update", "delete", "execute", "dump"}

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            op_name = _get_call_name(node)
            if op_name not in _DATA_OPS:
                continue

            # Check if the call is inside a try/except or context manager (with)
            has_integrity_check = _is_in_try_or_with(tree, node.lineno)

            suggestion = ""
            if not has_integrity_check:
                suggestion = (
                    f"Data operation '{op_name}' should be wrapped in a transaction "
                    "or try/except block to ensure data integrity on failure."
                )

            results.append({
                "line": node.lineno,
                "operation": op_name,
                "has_integrity_check": has_integrity_check,
                "suggestion": suggestion,
            })

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return ""


def _has_logging(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                name = _get_call_name(node)
                if name in ("error", "warning", "info", "debug", "critical", "exception", "log", "print"):
                    return True
    return False


def _has_reraise(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Raise):
                return True
    return False


def _has_return(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        if isinstance(stmt, ast.Return):
            return True
    return False


def _has_assignment(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            return True
    return False


def _loop_has_max_retries(node: ast.AST) -> bool:
    """Heuristic: loop has max_retries if condition or body references a max variable."""
    src = ast.unparse(node).lower()
    return any(k in src for k in ("max_retries", "max_attempts", "max_retry", "retries >=", "attempts >=", "< max"))


def _collect_mutations(stmts: list[ast.stmt]) -> list[tuple[int, str]]:
    """Find attribute/subscript mutations in statement list."""
    mutations: list[tuple[int, str]] = []
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute):
                        mutations.append((
                            node.lineno,
                            f"self.{target.attr} = ...",
                        ))
                    elif isinstance(target, ast.Subscript):
                        mutations.append((
                            node.lineno,
                            f"{ast.unparse(target.value)}[...] = ...",
                        ))
            elif isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Attribute):
                    mutations.append((
                        node.lineno,
                        f"self.{node.target.attr} augmented",
                    ))
    return mutations


def _handlers_have_rollback(handlers: list[ast.ExceptHandler]) -> bool:
    """Check if any handler body performs a rollback-like operation."""
    rollback_names = {"rollback", "restore", "reset", "undo", "revert"}
    for handler in handlers:
        for stmt in handler.body:
            for node in ast.walk(stmt):
                if isinstance(node, ast.Call):
                    name = _get_call_name(node)
                    if name in rollback_names:
                        return True
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute):
                            # Looks like restoring a previous value
                            return True
    return False


def _is_in_try_or_with(tree: ast.AST, target_line: int) -> bool:
    """Check if a line is inside a try/except or with block."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Try, ast.With)):
            start = node.lineno
            end = node.end_lineno or node.lineno
            if start <= target_line <= end:
                # Make sure the line is in the body (not just the handler)
                if isinstance(node, ast.Try):
                    body_end = (node.handlers[0].lineno - 1) if node.handlers else end
                    if start <= target_line <= body_end:
                        return True
                else:
                    return True
    return False
