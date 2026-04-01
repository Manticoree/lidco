"""REPL Enhancer — multiline detection, auto-indent, bracket matching, syntax highlight."""
from __future__ import annotations

import re

# Simple keyword-based highlighting (no external deps)
_PYTHON_KEYWORDS = {
    "def", "class", "return", "if", "elif", "else", "for", "while",
    "import", "from", "try", "except", "finally", "with", "as",
    "yield", "raise", "pass", "break", "continue", "lambda",
    "and", "or", "not", "in", "is", "True", "False", "None",
    "async", "await",
}

_JS_KEYWORDS = {
    "function", "const", "let", "var", "return", "if", "else",
    "for", "while", "class", "import", "export", "from", "try",
    "catch", "finally", "throw", "new", "this", "async", "await",
    "true", "false", "null", "undefined",
}

_KEYWORDS_BY_LANG: dict[str, set[str]] = {
    "python": _PYTHON_KEYWORDS,
    "javascript": _JS_KEYWORDS,
    "js": _JS_KEYWORDS,
}

_BRACKET_PAIRS: dict[str, str] = {"(": ")", "[": "]", "{": "}"}
_CLOSE_TO_OPEN: dict[str, str] = {v: k for k, v in _BRACKET_PAIRS.items()}


class REPLEnhancer:
    """Utility helpers for an enhanced REPL experience."""

    def __init__(
        self,
        enable_multiline: bool = True,
        enable_highlight: bool = True,
    ) -> None:
        self._enable_multiline = enable_multiline
        self._enable_highlight = enable_highlight

    # -- multiline detection ----------------------------------------------

    def is_multiline_input(self, text: str) -> bool:
        """Return ``True`` when *text* appears incomplete.

        Detects unclosed brackets ``( [ {`` and unterminated triple-quotes.
        """
        if not self._enable_multiline:
            return False

        # Check unclosed brackets
        stack: list[str] = []
        in_string: str | None = None
        i = 0
        while i < len(text):
            ch = text[i]

            # Handle triple-quote strings
            if text[i:i + 3] in ('"""', "'''"):
                tq = text[i:i + 3]
                if in_string == tq:
                    in_string = None
                    i += 3
                    continue
                if in_string is None:
                    in_string = tq
                    i += 3
                    continue

            # Handle single-char string delimiters
            if ch in ('"', "'") and in_string is None:
                in_string = ch
                i += 1
                continue
            if in_string and ch == in_string:
                in_string = None
                i += 1
                continue

            if in_string is None:
                if ch in _BRACKET_PAIRS:
                    stack.append(ch)
                elif ch in _CLOSE_TO_OPEN:
                    if stack and stack[-1] == _CLOSE_TO_OPEN[ch]:
                        stack.pop()

            i += 1

        if stack:
            return True

        # Check unterminated triple-quote
        if in_string is not None:
            return True

        return False

    # -- auto-indent ------------------------------------------------------

    def auto_indent(self, text: str, cursor_line: int) -> str:
        """Return *text* with the line at *cursor_line* auto-indented.

        Uses the previous line's indentation; adds 4 spaces after
        lines ending with ``:``.
        """
        lines = text.split("\n")
        if cursor_line <= 0 or cursor_line >= len(lines):
            return text

        prev = lines[cursor_line - 1]
        indent = len(prev) - len(prev.lstrip())
        if prev.rstrip().endswith(":"):
            indent += 4

        current = lines[cursor_line].lstrip()
        new_lines = list(lines)
        new_lines[cursor_line] = " " * indent + current
        return "\n".join(new_lines)

    # -- bracket matching -------------------------------------------------

    def match_bracket(self, text: str, pos: int) -> int | None:
        """Return the position of the matching bracket, or ``None``."""
        if pos < 0 or pos >= len(text):
            return None

        ch = text[pos]

        if ch in _BRACKET_PAIRS:
            target = _BRACKET_PAIRS[ch]
            depth = 0
            for i in range(pos, len(text)):
                if text[i] == ch:
                    depth += 1
                elif text[i] == target:
                    depth -= 1
                    if depth == 0:
                        return i
            return None

        if ch in _CLOSE_TO_OPEN:
            opener = _CLOSE_TO_OPEN[ch]
            depth = 0
            for i in range(pos, -1, -1):
                if text[i] == ch:
                    depth += 1
                elif text[i] == opener:
                    depth -= 1
                    if depth == 0:
                        return i
            return None

        return None

    # -- syntax highlighting ----------------------------------------------

    def highlight_syntax(self, text: str, language: str = "python") -> str:
        """Return *text* with ANSI escape codes for keyword highlighting.

        When highlighting is disabled, returns *text* unchanged.
        """
        if not self._enable_highlight:
            return text

        keywords = _KEYWORDS_BY_LANG.get(language, set())
        if not keywords:
            return text

        def _highlight_word(match: re.Match[str]) -> str:
            word = match.group(0)
            if word in keywords:
                return f"\033[1;34m{word}\033[0m"
            return word

        return re.sub(r"\b[a-zA-Z_]\w*\b", _highlight_word, text)
