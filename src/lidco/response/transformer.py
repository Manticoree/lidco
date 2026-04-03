"""Response transformer — dedup, cleanup, and rule-based transformations."""
from __future__ import annotations

import re


_CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


class ResponseTransformer:
    """Apply post-processing transformations to LLM response text."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def strip_redundant(text: str) -> str:
        """Remove immediately-repeated phrases (case-insensitive)."""
        words = text.split()
        if not words:
            return text
        result: list[str] = [words[0]]
        for w in words[1:]:
            if w.lower() != result[-1].lower():
                result.append(w)
        return " ".join(result)

    @staticmethod
    def format_code(text: str) -> str:
        """Normalize indentation inside fenced code blocks to 4-space."""

        def _normalize(m: re.Match[str]) -> str:
            lang = m.group(1)
            code = m.group(2)
            lines = code.splitlines(keepends=True)
            normalized: list[str] = []
            for line in lines:
                # Replace leading tabs with 4 spaces
                stripped = line.lstrip("\t")
                indent_count = len(line) - len(stripped)
                normalized.append("    " * indent_count + stripped)
            return f"```{lang}\n{''.join(normalized)}```"

        return _CODE_BLOCK_RE.sub(_normalize, text)

    @staticmethod
    def deduplicate(text: str) -> str:
        """Remove consecutive duplicate paragraphs."""
        paragraphs = re.split(r"\n{2,}", text)
        deduped: list[str] = []
        for p in paragraphs:
            stripped = p.strip()
            if not stripped:
                continue
            if deduped and stripped == deduped[-1]:
                continue
            deduped.append(stripped)
        return "\n\n".join(deduped)

    @staticmethod
    def apply_rules(text: str, rules: list[dict[str, str]]) -> str:
        """Apply transformation *rules* sequentially.

        Each rule is ``{"pattern": <regex>, "replacement": <str>}``.
        """
        result = text
        for rule in rules:
            pattern = rule.get("pattern", "")
            replacement = rule.get("replacement", "")
            if pattern:
                result = re.sub(pattern, replacement, result)
        return result

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def transform(self, text: str) -> str:
        """Apply all built-in transformations in order."""
        result = self.strip_redundant(text)
        result = self.format_code(result)
        result = self.deduplicate(result)
        return result
