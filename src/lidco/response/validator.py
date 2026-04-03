"""Response validator — completeness, syntax, and hallucination checks."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a response validation pass."""

    is_valid: bool
    issues: list[str] = field(default_factory=list)


_OPEN_CLOSE_PAIRS: list[tuple[str, str]] = [
    ("(", ")"),
    ("[", "]"),
    ("{", "}"),
]

_FILE_PATH_RE = re.compile(
    r"(?:^|\s)([A-Za-z]:)?(?:[/\\][\w.\-]+){2,}",
    re.MULTILINE,
)


class ResponseValidator:
    """Validate an LLM response for completeness and correctness."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def check_completeness(response: str) -> bool:
        """Return *True* if *response* looks complete.

        Heuristic: the response must end with a sentence-ending character
        (period, question mark, exclamation, backtick, colon, closing bracket,
        or closing paren) after stripping whitespace, and must not end mid-code
        fence.
        """
        text = response.rstrip()
        if not text:
            return False
        # Incomplete code fence (odd number of ```)
        fence_count = text.count("```")
        if fence_count % 2 != 0:
            return False
        last = text[-1]
        return last in ".?!`):]\""
    @staticmethod
    def check_code_syntax(code: str, language: str = "python") -> list[str]:
        """Basic bracket / quote matching for *code*.

        Returns a list of issue strings (empty means OK).
        """
        issues: list[str] = []
        for opener, closer in _OPEN_CLOSE_PAIRS:
            if code.count(opener) != code.count(closer):
                issues.append(
                    f"Mismatched '{opener}'/'{closer}': "
                    f"{code.count(opener)} open vs {code.count(closer)} close"
                )
        for q in ('"', "'"):
            # Ignore escaped quotes for a simple heuristic
            stripped = code.replace(f"\\{q}", "")
            if stripped.count(q) % 2 != 0:
                issues.append(f"Unmatched quote: {q}")
        return issues

    @staticmethod
    def detect_hallucinated_files(
        response: str,
        known_files: set[str],
    ) -> list[str]:
        """Return file paths mentioned in *response* but not in *known_files*."""
        mentioned: list[str] = []
        for m in _FILE_PATH_RE.finditer(response):
            path = m.group(0).strip()
            if path not in known_files:
                mentioned.append(path)
        return mentioned

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def validate(self, response: str) -> ValidationResult:
        """Run all validation checks and return a :class:`ValidationResult`."""
        issues: list[str] = []

        if not self.check_completeness(response):
            issues.append("Response appears incomplete")

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
        )
