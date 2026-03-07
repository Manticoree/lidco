"""Tests for syntax_fixer — SyntaxError pattern diagnoser."""

from __future__ import annotations

import pytest

from lidco.core.syntax_fixer import (
    SyntaxFix,
    diagnose_from_exc,
    diagnose_syntax_error,
    format_syntax_fix,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_exc(
    msg: str,
    lineno: int | None = 1,
    text: str | None = "",
    exc_type: type[SyntaxError] = SyntaxError,
) -> SyntaxError:
    exc = exc_type(msg)
    exc.lineno = lineno
    exc.text = text
    return exc


# ---------------------------------------------------------------------------
# diagnose_syntax_error — pattern matching
# ---------------------------------------------------------------------------


class TestMissingColon:
    def test_if_without_colon(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="expected ':'",
            lineno=5,
            source_line="if x > 0",
        )
        assert fix is not None
        assert fix.pattern == "missing-colon"
        assert fix.line == 5

    def test_def_without_colon(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="expected ':'",
            lineno=1,
            source_line="def foo()",
        )
        assert fix is not None
        assert fix.pattern == "missing-colon"

    def test_colon_fix_hint_present(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="expected ':'",
            lineno=3,
            source_line="while True",
        )
        assert fix is not None
        assert ":" in fix.fix_hint


class TestMissingPrintParens:
    def test_print_statement_detected(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="Missing parentheses in call to 'print'",
            lineno=2,
            source_line="print 'hello'",
        )
        assert fix is not None
        assert fix.pattern == "missing-print-parens"

    def test_fix_hint_shows_parens(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="Missing parentheses in call to 'print'",
            lineno=1,
            source_line="print x",
        )
        assert fix is not None
        assert "print(" in fix.fix_hint or "(" in fix.fix_hint


class TestUnexpectedEOF:
    def test_eof_bracket_error(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="unexpected EOF while parsing",
            lineno=10,
            source_line="data = [1, 2, 3",
        )
        assert fix is not None
        assert fix.pattern == "unexpected-eof"


class TestUnmatchedBracket:
    def test_was_never_closed(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="'(' was never closed",
            lineno=4,
            source_line="result = func(a, b",
        )
        assert fix is not None
        assert fix.pattern == "unmatched-bracket"

    def test_closing_parenthesis_error(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="unmatched ')'",
            lineno=7,
            source_line="result = (a + b))",
        )
        assert fix is not None
        assert fix.pattern == "unmatched-bracket"

    def test_unmatched_bracket(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="unmatched ']'",
            lineno=2,
            source_line="x = [1, 2]]",
        )
        assert fix is not None
        assert fix.pattern == "unmatched-bracket"

    def test_unmatched_brace(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="unmatched '}'",
            lineno=3,
            source_line="d = {'a': 1}}",
        )
        assert fix is not None
        assert fix.pattern == "unmatched-bracket"


class TestUnclosedString:
    def test_eol_string(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="EOL while scanning string literal",
            lineno=3,
            source_line='name = "hello',
        )
        assert fix is not None
        assert fix.pattern == "unclosed-string"

    def test_eof_string(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="EOF while scanning triple-quoted string literal",
            lineno=5,
            source_line='doc = """',
        )
        assert fix is not None
        assert fix.pattern == "unclosed-string"

    def test_eof_scanning_string(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="EOF while scanning string literal",
            lineno=2,
            source_line='x = "unclosed',
        )
        assert fix is not None
        assert fix.pattern == "unclosed-string"


class TestInvalidEscape:
    def test_invalid_escape_sequence(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="invalid escape sequence '\\p'",
            lineno=2,
            source_line=r'path = "C:\program files"',
        )
        assert fix is not None
        assert fix.pattern == "invalid-escape"

    def test_fix_hint_mentions_raw_string(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="invalid escape sequence '\\n'",
            lineno=1,
            source_line=r'x = "\name"',
        )
        assert fix is not None
        assert "r\"" in fix.fix_hint or "raw" in fix.fix_hint.lower() or "\\\\" in fix.fix_hint


class TestFStringError:
    def test_fstring_expression_error(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="f-string: invalid syntax",
            lineno=4,
            source_line='msg = f"value: {x:}"',
        )
        assert fix is not None
        assert fix.pattern == "fstring-error"

    def test_fstring_backslash_error(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="f-string expression part cannot include a backslash",
            lineno=2,
            source_line=r'x = f"path: {path\name}"',
        )
        assert fix is not None
        assert fix.pattern == "fstring-error"


class TestIndentationError:
    def test_unexpected_indent(self):
        fix = diagnose_syntax_error(
            error_type="IndentationError",
            error_msg="unexpected indent",
            lineno=6,
            source_line="    x = 1",
        )
        assert fix is not None
        assert fix.pattern == "indentation-error"

    def test_expected_indented_block(self):
        fix = diagnose_syntax_error(
            error_type="IndentationError",
            error_msg="expected an indented block",
            lineno=3,
            source_line="pass",
        )
        assert fix is not None
        assert fix.pattern == "indentation-error"

    def test_inconsistent_use_of_tabs(self):
        fix = diagnose_syntax_error(
            error_type="TabError",
            error_msg="inconsistent use of tabs and spaces in indentation",
            lineno=8,
            source_line="\t  x = 1",
        )
        assert fix is not None
        assert fix.pattern == "indentation-error"

    def test_fix_hint_mentions_indent(self):
        fix = diagnose_syntax_error(
            error_type="IndentationError",
            error_msg="unexpected indent",
            lineno=1,
            source_line="    pass",
        )
        assert fix is not None
        assert "indent" in fix.fix_hint.lower() or "spaces" in fix.fix_hint.lower() or "tab" in fix.fix_hint.lower()


class TestInvalidAssignment:
    def test_cannot_assign_to_literal(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="cannot assign to literal",
            lineno=5,
            source_line="1 = x",
        )
        assert fix is not None
        assert fix.pattern == "invalid-assignment"

    def test_cannot_assign_to_function_call(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="cannot assign to function call",
            lineno=3,
            source_line="foo() = 1",
        )
        assert fix is not None
        assert fix.pattern == "invalid-assignment"

    def test_augmented_assign_operator_confusion(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="invalid syntax",
            lineno=1,
            source_line="x =+ 1",
        )
        # May or may not detect this — just must not raise
        assert isinstance(fix, (SyntaxFix, type(None)))


# ---------------------------------------------------------------------------
# No pattern matched — returns None
# ---------------------------------------------------------------------------


class TestNoPatternMatch:
    def test_unknown_error_returns_none(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="completely unknown error message xyz",
            lineno=1,
            source_line="some code",
        )
        assert fix is None

    def test_none_error_msg_returns_none(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg=None,  # type: ignore[arg-type]
            lineno=1,
            source_line=None,
        )
        assert fix is None

    def test_indent_msg_with_syntax_error_type_returns_none(self):
        # indentation-error pattern requires error_type in ("IndentationError", "TabError")
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="unexpected indent",
            lineno=1,
            source_line="    x = 1",
        )
        assert fix is None

    def test_none_source_line_allowed(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="expected ':'",
            lineno=1,
            source_line=None,
        )
        # Should still match on message alone
        assert fix is not None
        assert fix.pattern == "missing-colon"

    def test_none_lineno_allowed(self):
        fix = diagnose_syntax_error(
            error_type="SyntaxError",
            error_msg="Missing parentheses in call to 'print'",
            lineno=None,
            source_line="print 'hello'",
        )
        assert fix is not None
        assert fix.line is None


# ---------------------------------------------------------------------------
# diagnose_from_exc — exception wrapper
# ---------------------------------------------------------------------------


class TestDiagnoseFromExc:
    def test_syntax_error_exc(self):
        exc = _make_exc("expected ':'", lineno=4, text="if x > 0")
        fix = diagnose_from_exc(exc)
        assert fix is not None
        assert fix.pattern == "missing-colon"
        assert fix.line == 4

    def test_indentation_error_exc(self):
        exc = _make_exc(
            "unexpected indent",
            lineno=2,
            text="    x = 1",
            exc_type=IndentationError,
        )
        fix = diagnose_from_exc(exc)
        assert fix is not None
        assert fix.pattern == "indentation-error"

    def test_no_match_returns_none(self):
        exc = _make_exc("unknown weird error", lineno=1, text="code")
        fix = diagnose_from_exc(exc)
        assert fix is None


# ---------------------------------------------------------------------------
# SyntaxFix dataclass
# ---------------------------------------------------------------------------


class TestSyntaxFixDataclass:
    def test_is_frozen(self):
        fix = SyntaxFix(
            pattern="missing-colon",
            description="Missing colon",
            fix_hint="Add ':' at end of line",
            confidence=0.9,
            line=1,
        )
        with pytest.raises((AttributeError, TypeError)):
            fix.pattern = "other"  # type: ignore[misc]

    def test_fields_accessible(self):
        fix = SyntaxFix(
            pattern="test",
            description="desc",
            fix_hint="hint",
            confidence=0.5,
            line=None,
        )
        assert fix.pattern == "test"
        assert fix.description == "desc"
        assert fix.fix_hint == "hint"
        assert fix.confidence == 0.5
        assert fix.line is None


# ---------------------------------------------------------------------------
# format_syntax_fix
# ---------------------------------------------------------------------------


class TestFormatSyntaxFix:
    def test_output_contains_pattern(self):
        fix = SyntaxFix(
            pattern="missing-colon",
            description="Missing colon at end of statement",
            fix_hint="Add ':' at end of the line",
            confidence=0.95,
            line=5,
        )
        result = format_syntax_fix(fix)
        assert "missing-colon" in result
        assert "Add ':'" in result or "colon" in result.lower()

    def test_output_contains_line_number(self):
        fix = SyntaxFix(
            pattern="indentation-error",
            description="Unexpected indent",
            fix_hint="Check indentation",
            confidence=0.9,
            line=12,
        )
        result = format_syntax_fix(fix)
        assert "12" in result

    def test_no_line_number_when_none(self):
        fix = SyntaxFix(
            pattern="missing-print-parens",
            description="Missing parentheses",
            fix_hint="Use print(x)",
            confidence=1.0,
            line=None,
        )
        result = format_syntax_fix(fix)
        # Should not crash, and should not contain "None"
        assert "None" not in result
        assert isinstance(result, str)
        assert len(result) > 0

    def test_confidence_shown(self):
        fix = SyntaxFix(
            pattern="fstring-error",
            description="f-string syntax issue",
            fix_hint="Check expression inside braces",
            confidence=0.8,
            line=3,
        )
        result = format_syntax_fix(fix)
        # Confidence value or percentage should appear
        assert "0.8" in result or "80" in result
