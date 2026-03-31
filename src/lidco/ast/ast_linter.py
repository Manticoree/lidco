"""AST-aware lint-after-edit — Task 930."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from lidco.ast.treesitter_parser import TreeSitterParser, HAS_TREESITTER


@dataclass
class LintResult:
    """Result of linting a source file."""

    file_path: str
    language: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    valid: bool = True


class ASTLinter:
    """Lint source files using AST analysis.

    Uses tree-sitter ERROR nodes when available, otherwise falls back to
    ``compile()`` for Python and bracket matching for others.
    """

    def __init__(self, parser: TreeSitterParser) -> None:
        self._parser = parser

    def lint(
        self, source: str, language: str, file_path: str = ""
    ) -> LintResult:
        """Lint *source* in *language*."""
        if HAS_TREESITTER and self._parser.is_available():
            return self._lint_treesitter(source, language, file_path)
        return self._lint_fallback(source, language, file_path)

    def lint_file(
        self, file_path: str, read_fn: Callable[[str], str] | None = None
    ) -> LintResult:
        """Lint a file on disk."""
        reader = read_fn or self._default_read
        try:
            source = reader(file_path)
        except Exception as exc:
            return LintResult(
                file_path=file_path,
                language="unknown",
                errors=[f"Cannot read file: {exc}"],
                valid=False,
            )

        language = self._parser.detect_language(file_path) or "unknown"
        result = self.lint(source, language, file_path)
        return LintResult(
            file_path=file_path,
            language=result.language,
            errors=result.errors,
            warnings=result.warnings,
            valid=result.valid,
        )

    def auto_fix_suggestions(self, result: LintResult) -> list[str]:
        """Return suggested fixes for common errors."""
        suggestions: list[str] = []
        for error in result.errors:
            lower = error.lower()
            if "unexpected indent" in lower or "indent" in lower:
                suggestions.append("Check indentation — mix of tabs and spaces?")
            elif "unterminated string" in lower or "string" in lower:
                suggestions.append("Check for unclosed string literal (missing quote).")
            elif "expected" in lower and ")" in lower:
                suggestions.append("Missing closing parenthesis.")
            elif "expected" in lower and "}" in lower:
                suggestions.append("Missing closing brace.")
            elif "bracket" in lower or "paren" in lower:
                suggestions.append("Mismatched brackets or parentheses.")
            elif "syntax" in lower:
                suggestions.append("General syntax error — review the indicated line.")
        return suggestions

    # ------------------------------------------------------------------
    # Tree-sitter backend
    # ------------------------------------------------------------------

    def _lint_treesitter(
        self, source: str, language: str, file_path: str
    ) -> LintResult:
        parse_result = self._parser.parse(source, language)
        return LintResult(
            file_path=file_path,
            language=language,
            errors=list(parse_result.errors),
            warnings=[],
            valid=len(parse_result.errors) == 0,
        )

    # ------------------------------------------------------------------
    # Fallback linter
    # ------------------------------------------------------------------

    def _lint_fallback(
        self, source: str, language: str, file_path: str
    ) -> LintResult:
        errors: list[str] = []
        warnings: list[str] = []

        if language == "python":
            try:
                compile(source, file_path or "<string>", "exec")
            except SyntaxError as exc:
                errors.append(
                    f"SyntaxError: {exc.msg} (line {exc.lineno})"
                )

        # Bracket matching for all languages
        bracket_errors = self._check_brackets(source)
        errors.extend(bracket_errors)

        # Trailing whitespace warnings
        for i, line in enumerate(source.splitlines(), 1):
            if line != line.rstrip() and line.strip():
                warnings.append(f"Trailing whitespace on line {i}")

        return LintResult(
            file_path=file_path,
            language=language,
            errors=errors,
            warnings=warnings,
            valid=len(errors) == 0,
        )

    @staticmethod
    def _check_brackets(source: str) -> list[str]:
        """Check for mismatched brackets/parens/braces."""
        stack: list[tuple[str, int]] = []
        openers = {"(": ")", "[": "]", "{": "}"}
        closers = {")": "(", "]": "[", "}": "{"}
        errors: list[str] = []

        in_string = False
        string_char = ""
        escaped = False
        line_num = 1

        for ch in source:
            if ch == "\n":
                line_num += 1
                continue
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if in_string:
                if ch == string_char:
                    in_string = False
                continue
            if ch in ('"', "'"):
                in_string = True
                string_char = ch
                continue
            if ch in openers:
                stack.append((ch, line_num))
            elif ch in closers:
                expected_opener = closers[ch]
                if not stack:
                    errors.append(
                        f"Unmatched closing '{ch}' at line {line_num}"
                    )
                elif stack[-1][0] != expected_opener:
                    errors.append(
                        f"Mismatched bracket: expected closing for "
                        f"'{stack[-1][0]}' (line {stack[-1][1]}) but found "
                        f"'{ch}' at line {line_num}"
                    )
                    stack.pop()
                else:
                    stack.pop()

        for opener, ln in stack:
            errors.append(
                f"Unclosed '{opener}' opened at line {ln}"
            )

        return errors

    @staticmethod
    def _default_read(path: str) -> str:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
