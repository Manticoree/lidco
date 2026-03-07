"""SyntaxError pattern diagnoser — matches Python syntax errors to named fixes.

Recognises 9 named patterns and returns a structured :class:`SyntaxFix` with
a human-readable description, a concrete fix hint, and a confidence score.

Usage::

    try:
        compile(source, "<string>", "exec")
    except SyntaxError as exc:
        fix = diagnose_from_exc(exc)
        if fix:
            print(format_syntax_fix(fix))
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SyntaxFix:
    """A matched syntax pattern with repair guidance.

    Attributes:
        pattern:     Short slug identifying the named pattern (e.g. ``"missing-colon"``).
        description: One-line human explanation of the error.
        fix_hint:    Concrete suggestion for fixing the issue.
        confidence:  Float in ``[0, 1]`` indicating pattern match certainty.
        line:        Source line number from the exception (may be ``None``).
    """

    pattern: str
    description: str
    fix_hint: str
    confidence: float
    line: int | None


# ---------------------------------------------------------------------------
# Internal pattern table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pattern:
    """Internal rule used by the matcher."""

    pattern: str
    description: str
    fix_hint: str
    confidence: float
    # Substrings to match against the error message (case-insensitive, ANY matches)
    msg_substrings: tuple[str, ...]
    # Optional error type restriction (e.g. "IndentationError").  Empty means any.
    error_types: tuple[str, ...]


_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern(
        pattern="missing-print-parens",
        description="Python 2-style 'print' statement without parentheses.",
        fix_hint="Use print() with parentheses: print(value).",
        confidence=1.0,
        msg_substrings=("missing parentheses in call to 'print'",),
        error_types=(),
    ),
    _Pattern(
        pattern="missing-colon",
        description="Missing ':' at the end of a compound statement header.",
        fix_hint=(
            "Add ':' at the end of the line (e.g. 'if x > 0:' / 'def foo():')."
        ),
        confidence=0.95,
        msg_substrings=("expected ':'",),
        error_types=(),
    ),
    _Pattern(
        pattern="unmatched-bracket",
        description="Bracket, parenthesis or brace was opened but never closed, or extra closing bracket.",
        fix_hint=(
            "Check that every '(', '[', and '{' has a matching closing counterpart. "
            "Use an editor with bracket highlighting."
        ),
        confidence=0.9,
        msg_substrings=(
            "was never closed",
            "unmatched ')'",
            "unmatched ']'",
            "unmatched '}'",
        ),
        error_types=(),
    ),
    _Pattern(
        pattern="unclosed-string",
        description="String literal was opened but never closed.",
        fix_hint=(
            "Add the matching closing quote. "
            "For triple-quoted strings (\"\"\"...\"\"\" or '''...''') ensure all three quotes are present."
        ),
        confidence=0.95,
        msg_substrings=(
            "eol while scanning string literal",
            "eof while scanning string literal",
            "eof while scanning triple-quoted string literal",
        ),
        error_types=(),
    ),
    _Pattern(
        pattern="fstring-error",
        description="Invalid expression inside an f-string.",
        fix_hint=(
            "Check the expression inside braces. "
            "Backslashes are not allowed inside f-string expressions — "
            "assign to a variable first and reference it."
        ),
        confidence=0.9,
        msg_substrings=(
            "f-string: invalid syntax",
            "f-string expression part cannot include a backslash",
            "f-string: unmatched",
            "f-string:",
        ),
        error_types=(),
    ),
    _Pattern(
        pattern="invalid-escape",
        description="Invalid escape sequence in a string literal.",
        fix_hint=(
            r'Use a raw string (r"...") for paths or regex, '
            r'or double the backslash (\\).'
        ),
        confidence=0.95,
        msg_substrings=("invalid escape sequence",),
        error_types=(),
    ),
    _Pattern(
        pattern="indentation-error",
        description="Indentation is inconsistent or unexpected.",
        fix_hint=(
            "Ensure consistent indentation (4 spaces per level recommended). "
            "Do not mix tabs and spaces. "
            "Run: python -m tabnanny <file> to detect tab/space mixing."
        ),
        confidence=0.95,
        msg_substrings=(
            "unexpected indent",
            "expected an indented block",
            "unindent does not match",
            "inconsistent use of tabs and spaces",
        ),
        error_types=("IndentationError", "TabError"),
    ),
    _Pattern(
        pattern="unexpected-eof",
        description="Unexpected end-of-file — likely an unclosed bracket or incomplete expression.",
        fix_hint=(
            "Check for unclosed '(', '[', or '{'. "
            "Ensure the last statement is complete."
        ),
        confidence=0.85,
        msg_substrings=("unexpected eof while parsing",),
        error_types=(),
    ),
    _Pattern(
        pattern="invalid-assignment",
        description="Assignment to a non-assignable target (literal, call, etc.).",
        fix_hint=(
            "Ensure the left-hand side of '=' is a valid target: "
            "a variable name, attribute, or subscript. "
            "Did you mean '==' for comparison?"
        ),
        confidence=0.9,
        msg_substrings=(
            "cannot assign to literal",
            "cannot assign to function call",
            "cannot assign to expression",
            "cannot assign to operator",
        ),
        error_types=(),
    ),
)


# ---------------------------------------------------------------------------
# Core diagnostic function
# ---------------------------------------------------------------------------


def diagnose_syntax_error(
    error_type: str,
    error_msg: str,
    lineno: int | None,
    source_line: str | None,
) -> SyntaxFix | None:
    """Match a SyntaxError to a named pattern and return repair guidance.

    Args:
        error_type:  ``type(exc).__name__`` — e.g. ``"SyntaxError"``,
                     ``"IndentationError"``, ``"TabError"``.
        error_msg:   ``str(exc)`` — the error message text.
        lineno:      ``exc.lineno`` — may be ``None``.
        source_line: ``exc.text`` — may be ``None``.  Reserved for future
                     context-aware pattern matching (e.g. detecting ``x =+ 1``
                     operator confusion from the raw source text).

    Returns:
        A :class:`SyntaxFix` when a pattern matches, otherwise ``None``.
    """
    msg_lower = error_msg.lower() if error_msg else ""

    for pat in _PATTERNS:
        # Optional error-type filter
        if pat.error_types and error_type not in pat.error_types:
            continue

        # Message substring match (case-insensitive, ANY)
        if not any(sub in msg_lower for sub in pat.msg_substrings):
            continue

        return SyntaxFix(
            pattern=pat.pattern,
            description=pat.description,
            fix_hint=pat.fix_hint,
            confidence=pat.confidence,
            line=lineno,
        )

    return None


def diagnose_from_exc(exc: SyntaxError) -> SyntaxFix | None:
    """Convenience wrapper around :func:`diagnose_syntax_error` for ``SyntaxError`` instances.

    Args:
        exc: A :class:`SyntaxError` (or subclass) instance.

    Returns:
        A :class:`SyntaxFix` when a pattern matches, otherwise ``None``.
    """
    return diagnose_syntax_error(
        error_type=type(exc).__name__,
        error_msg=str(exc),
        lineno=getattr(exc, "lineno", None),
        source_line=getattr(exc, "text", None),
    )


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def format_syntax_fix(fix: SyntaxFix) -> str:
    """Format a :class:`SyntaxFix` as a Markdown snippet.

    Returns a multi-line string suitable for display in the debug pipeline.
    """
    pct = int(fix.confidence * 100)
    line_info = f" (line {fix.line})" if fix.line is not None else ""
    return (
        f"[SyntaxFix: {fix.pattern}]{line_info} — confidence {pct}%\n"
        f"  {fix.description}\n"
        f"  Fix: {fix.fix_hint}"
    )
