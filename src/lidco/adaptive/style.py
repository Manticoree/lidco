"""StyleTransfer — detect and match coding style conventions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class StyleProfile:
    """Detected coding style information."""

    naming: str = "unknown"  # snake_case | camelCase | PascalCase | UPPER_SNAKE | mixed
    comment_style: str = "unknown"  # hash | slash | docstring | none
    indent: str = "unknown"  # spaces_2 | spaces_4 | tabs | mixed
    line_length_avg: float = 0.0
    blank_line_ratio: float = 0.0


_SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")
_CAMEL_RE = re.compile(r"^[a-z][a-zA-Z0-9]*$")
_PASCAL_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
_UPPER_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$")

# Patterns to extract identifiers from code
_IDENT_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")
_KEYWORDS = frozenset({
    "def", "class", "if", "else", "elif", "for", "while", "return", "import",
    "from", "try", "except", "finally", "with", "as", "yield", "raise",
    "pass", "break", "continue", "and", "or", "not", "in", "is", "None",
    "True", "False", "lambda", "global", "nonlocal", "assert", "del",
    "var", "let", "const", "function", "new", "this", "typeof", "instanceof",
    "void", "null", "undefined", "async", "await", "self", "print",
})


class StyleTransfer:
    """Detect and match coding style."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, code: str) -> dict[str, object]:
        """Analyze *code* and return a style profile as a dict."""
        profile = self._build_profile(code)
        return {
            "naming": profile.naming,
            "comment_style": profile.comment_style,
            "indent": profile.indent,
            "line_length_avg": round(profile.line_length_avg, 1),
            "blank_line_ratio": round(profile.blank_line_ratio, 3),
        }

    def detect_naming(self, code: str) -> str:
        """Detect the dominant naming convention in *code*."""
        identifiers = self._extract_identifiers(code)
        return self._classify_naming(identifiers)

    def match(self, code: str, style: dict[str, object]) -> str:
        """Transform *code* to match the given *style* dict.

        Currently handles naming convention conversion.
        """
        target_naming = str(style.get("naming", ""))
        if not target_naming or target_naming == "unknown":
            return code

        result = code
        if target_naming == "snake_case":
            result = self._to_snake_case(result)
        elif target_naming == "camelCase":
            result = self._to_camel_case(result)
        return result

    # ------------------------------------------------------------------
    # Profile building
    # ------------------------------------------------------------------

    def _build_profile(self, code: str) -> StyleProfile:
        lines = code.splitlines()
        if not lines:
            return StyleProfile()

        identifiers = self._extract_identifiers(code)
        naming = self._classify_naming(identifiers)
        comment_style = self._detect_comment_style(lines)
        indent = self._detect_indent(lines)

        non_empty = [ln for ln in lines if ln.strip()]
        line_length_avg = sum(len(ln) for ln in non_empty) / max(len(non_empty), 1)
        blank_count = sum(1 for ln in lines if not ln.strip())
        blank_line_ratio = blank_count / max(len(lines), 1)

        return StyleProfile(
            naming=naming,
            comment_style=comment_style,
            indent=indent,
            line_length_avg=line_length_avg,
            blank_line_ratio=blank_line_ratio,
        )

    # ------------------------------------------------------------------
    # Identifier extraction & classification
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_identifiers(code: str) -> list[str]:
        raw = _IDENT_RE.findall(code)
        return [w for w in raw if w not in _KEYWORDS and len(w) > 1 and not w.startswith("_")]

    @staticmethod
    def _classify_naming(identifiers: list[str]) -> str:
        if not identifiers:
            return "unknown"

        counts: dict[str, int] = {
            "snake_case": 0,
            "camelCase": 0,
            "PascalCase": 0,
            "UPPER_SNAKE": 0,
            "other": 0,
        }
        for ident in identifiers:
            if _SNAKE_RE.match(ident):
                counts["snake_case"] += 1
            elif _UPPER_SNAKE_RE.match(ident):
                counts["UPPER_SNAKE"] += 1
            elif _PASCAL_RE.match(ident):
                counts["PascalCase"] += 1
            elif _CAMEL_RE.match(ident):
                counts["camelCase"] += 1
            else:
                counts["other"] += 1

        best = max(counts, key=lambda k: counts[k])
        if counts[best] == 0:
            return "unknown"
        # If "other" dominates, call it mixed
        if best == "other":
            return "mixed"
        return best

    # ------------------------------------------------------------------
    # Comment & indent detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_comment_style(lines: list[str]) -> str:
        has_hash = any(line.lstrip().startswith("#") for line in lines)
        has_slash = any(line.lstrip().startswith("//") for line in lines)
        has_docstring = any('"""' in line or "'''" in line for line in lines)

        if has_docstring:
            return "docstring"
        if has_hash:
            return "hash"
        if has_slash:
            return "slash"
        return "none"

    @staticmethod
    def _detect_indent(lines: list[str]) -> str:
        indented = [line for line in lines if line and line[0] in (" ", "\t")]
        if not indented:
            return "unknown"

        has_tabs = any(line.startswith("\t") for line in indented)
        has_spaces = any(line.startswith(" ") for line in indented)

        if has_tabs and has_spaces:
            return "mixed"
        if has_tabs:
            return "tabs"

        # Detect space width
        widths: list[int] = []
        for line in indented:
            stripped = line.lstrip(" ")
            width = len(line) - len(stripped)
            if width > 0:
                widths.append(width)

        if not widths:
            return "spaces_4"

        avg_width = sum(widths) / len(widths)
        if avg_width <= 2.5:
            return "spaces_2"
        return "spaces_4"

    # ------------------------------------------------------------------
    # Naming conversions
    # ------------------------------------------------------------------

    @staticmethod
    def _to_snake_case(code: str) -> str:
        """Convert camelCase identifiers to snake_case in code."""

        def _convert(m: re.Match[str]) -> str:
            word = m.group(0)
            if word in _KEYWORDS or word.startswith("_") or len(word) <= 1:
                return word
            if not _CAMEL_RE.match(word):
                return word
            # Insert underscores before uppercase letters
            result = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", word)
            return result.lower()

        return _IDENT_RE.sub(_convert, code)

    @staticmethod
    def _to_camel_case(code: str) -> str:
        """Convert snake_case identifiers to camelCase in code."""

        def _convert(m: re.Match[str]) -> str:
            word = m.group(0)
            if word in _KEYWORDS or word.startswith("_") or len(word) <= 1:
                return word
            if not _SNAKE_RE.match(word):
                return word
            parts = word.split("_")
            return parts[0] + "".join(p.capitalize() for p in parts[1:])

        return _IDENT_RE.sub(_convert, code)
