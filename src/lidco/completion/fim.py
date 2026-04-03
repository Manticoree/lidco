"""Fill-in-the-middle completion."""
from __future__ import annotations

import re


class FillInMiddle:
    """Generate placeholder fill text between a prefix and suffix."""

    def __init__(self) -> None:
        self._multiline: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fill(self, prefix: str, suffix: str, indent: str = "") -> str:
        """Return a placeholder fill between *prefix* and *suffix*.

        The result is indented with *indent* if provided.
        """
        if not prefix and not suffix:
            return ""

        # Infer a simple placeholder based on surrounding text
        body = self._infer_body(prefix, suffix)
        if indent:
            lines = body.split("\n")
            body = "\n".join(
                (indent + line if line.strip() else line) for line in lines
            )
        return body

    def detect_indent(self, text: str) -> str:
        """Detect the indentation style used in *text*."""
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped and line != stripped:
                ws = line[: len(line) - len(stripped)]
                return ws
        return ""

    def suggest(self, prefix: str, suffix: str) -> list[str]:
        """Return multiple fill suggestions."""
        primary = self.fill(prefix, suffix)
        if not primary:
            return []
        suggestions = [primary]
        # Offer a pass/... alternative
        alt = "pass" if "\n" not in primary else "..."
        suggestions.append(alt)
        return suggestions

    @property
    def supports_multiline(self) -> bool:
        """Whether the engine supports multiline fill."""
        return self._multiline

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _infer_body(self, prefix: str, suffix: str) -> str:
        """Heuristic placeholder generation."""
        # If prefix ends with a function def, produce a return stub
        if re.search(r"def\s+\w+\s*\(.*\)\s*(->\s*\S+)?\s*:\s*$", prefix):
            return "pass"
        # If prefix ends with an if/elif/else, produce a pass
        if re.search(r"(if|elif|else)\s*.*:\s*$", prefix):
            return "pass"
        # If prefix ends with a class header, produce a docstring + pass
        if re.search(r"class\s+\w+.*:\s*$", prefix):
            return '"""..."""\n\npass'
        # If suffix starts with closing bracket, return empty
        if suffix.lstrip().startswith(")") or suffix.lstrip().startswith("]"):
            return ""
        # Generic: produce a comment placeholder
        return "# TODO: implement"
