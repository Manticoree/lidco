"""
Error Message Standardizer.

Audits error/exception messages for consistency, i18n-readiness, generates
error code templates, and suggests error codes.
"""
from __future__ import annotations

import ast
import re
import textwrap


class ErrorMessageStandardizer:
    """Audits and standardizes error messages in Python source code."""

    def __init__(self) -> None:
        self._code_counter = 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def audit_messages(self, source_code: str) -> list[dict]:
        """Find all error/exception messages and check consistency.

        Returns dicts with: line, message, issues (list of strings).
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        for node in ast.walk(tree):
            msg, line = _extract_exception_message(node)
            if msg is None:
                continue
            issues: list[str] = []
            if msg and msg[0].islower():
                issues.append("starts_lowercase")
            if msg and not msg.endswith(".") and not msg.endswith("!") and not msg.endswith("?"):
                issues.append("no_period")
            # Check if message embeds a traceback-like pattern
            if re.search(r"Traceback|File \".*\", line \d+", msg):
                issues.append("contains_stacktrace")
            results.append({
                "line": line,
                "message": msg,
                "issues": issues,
            })

        return results

    def check_i18n_readiness(self, source_code: str) -> list[dict]:
        """Check if error messages are i18n-ready.

        Returns dicts with: line, message, i18n_ready (bool), suggestion.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        for node in ast.walk(tree):
            msg, line = _extract_exception_message(node)
            if msg is None:
                continue

            # i18n-ready means wrapped in _() or has placeholder params
            i18n_ready = False
            suggestion = ""

            # Check if the raise/exception is wrapped in _() or gettext()
            if isinstance(node, ast.Raise) and node.exc is not None:
                exc = node.exc
                if isinstance(exc, ast.Call):
                    for arg in exc.args:
                        if isinstance(arg, ast.Call):
                            func_name = ""
                            if isinstance(arg.func, ast.Name):
                                func_name = arg.func.id
                            if func_name in ("_", "gettext", "ngettext"):
                                i18n_ready = True

            if not i18n_ready and msg:
                # Accept f-strings / .format() as templates (partial readiness)
                if "{" in msg and "}" in msg:
                    i18n_ready = True
                else:
                    suggestion = (
                        f"Wrap the message in _() for i18n: "
                        f"raise ExceptionType(_(\"{msg}\"))"
                    )

            results.append({
                "line": line,
                "message": msg,
                "i18n_ready": i18n_ready,
                "suggestion": suggestion,
            })

        return results

    def generate_templates(self, messages: list[str]) -> dict[str, str]:
        """Create error code -> template mapping from a list of messages.

        Replaces variable parts (quoted strings, numbers, identifiers that
        look like values) with {placeholder} tokens.
        """
        templates: dict[str, str] = {}
        counter = 1
        for msg in messages:
            template = _to_template(msg)
            code = f"ERR{counter:03d}"
            templates[code] = template
            counter += 1
        return templates

    def assign_error_codes(self, source_code: str) -> list[dict]:
        """Find exceptions and suggest error codes.

        Returns dicts with: line, exception_type, suggested_code, message.
        """
        results: list[dict] = []
        try:
            tree = ast.parse(textwrap.dedent(source_code))
        except SyntaxError:
            return results

        counter = 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.exc is not None:
                exc = node.exc
                exc_type = "Exception"
                message = ""
                if isinstance(exc, ast.Call):
                    if isinstance(exc.func, ast.Name):
                        exc_type = exc.func.id
                    elif isinstance(exc.func, ast.Attribute):
                        exc_type = exc.func.attr
                    if exc.args:
                        first_arg = exc.args[0]
                        message = _const_str(first_arg)
                elif isinstance(exc, ast.Name):
                    exc_type = exc.id

                code = f"ERR{counter:03d}"
                results.append({
                    "line": node.lineno,
                    "exception_type": exc_type,
                    "suggested_code": code,
                    "message": message,
                })
                counter += 1

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_exception_message(node: ast.AST) -> tuple[str | None, int]:
    """Extract the string message from a Raise node, if present."""
    if not isinstance(node, ast.Raise):
        return None, 0
    if node.exc is None:
        return None, 0
    exc = node.exc
    line = node.lineno
    if isinstance(exc, ast.Call) and exc.args:
        msg = _const_str(exc.args[0])
        if msg is not None:
            return msg, line
    return None, 0


def _const_str(node: ast.AST) -> str | None:
    """Return string constant from a node, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        # f-string: reconstruct approximate text
        parts: list[str] = []
        for val in node.values:
            if isinstance(val, ast.Constant):
                parts.append(str(val.value))
            else:
                parts.append("{...}")
        return "".join(parts)
    return None


_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
_NUMBER_RE = re.compile(r"\b\d+\b")
_PATH_RE = re.compile(r"/[\w/.-]+")


def _to_template(msg: str) -> str:
    """Convert a concrete message to a parameterised template."""
    result = _QUOTED_RE.sub("{value}", msg)
    result = _PATH_RE.sub("{path}", result)
    result = _NUMBER_RE.sub("{n}", result)
    return result
