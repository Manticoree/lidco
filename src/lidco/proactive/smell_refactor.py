"""Code smell auto-refactor — Task 416."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lidco.analysis.refactor_scanner import RefactorCandidate, RefactorScanner

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class RefactorSuggestion:
    """A suggested refactoring for a code smell."""

    candidate: RefactorCandidate
    before_snippet: str
    after_snippet: str
    explanation: str


class SmellRefactorer:
    """Wrap RefactorScanner and generate LLM-assisted refactoring suggestions."""

    def __init__(self, session: Any = None) -> None:
        self._scanner = RefactorScanner()
        self._session = session

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def find_smells(self, file_path: str) -> list[RefactorCandidate]:
        """Scan *file_path* for refactoring candidates."""
        try:
            source = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return []
        return self._scanner.scan(source, file_path)

    async def suggest_refactors(self, file_path: str) -> list[RefactorSuggestion]:
        """Return LLM-generated suggestions for each code smell in *file_path*."""
        try:
            source = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return []

        candidates = self._scanner.scan(source, file_path)
        if not candidates:
            return []

        lines = source.splitlines()
        suggestions: list[RefactorSuggestion] = []

        for candidate in candidates:
            snippet = self._extract_snippet(lines, candidate.line)
            after, explanation = await self._llm_suggest(candidate, snippet)
            suggestions.append(RefactorSuggestion(
                candidate=candidate,
                before_snippet=snippet,
                after_snippet=after,
                explanation=explanation,
            ))

        return suggestions

    def apply_suggestion(self, file_path: str, suggestion: RefactorSuggestion) -> bool:
        """Replace *before_snippet* with *after_snippet* in file.

        Returns True if the replacement was made.
        """
        try:
            source = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return False

        before = suggestion.before_snippet
        after = suggestion.after_snippet

        if before not in source or not after.strip():
            return False

        new_source = source.replace(before, after, 1)
        Path(file_path).write_text(new_source, encoding="utf-8")
        return True

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _extract_snippet(self, lines: list[str], start_line: int, context: int = 10) -> str:
        """Extract up to *context* lines starting from *start_line* (1-indexed)."""
        idx = max(0, start_line - 1)
        end = min(len(lines), idx + context)
        return "\n".join(lines[idx:end])

    async def _llm_suggest(
        self,
        candidate: RefactorCandidate,
        snippet: str,
    ) -> tuple[str, str]:
        """Ask LLM for a refactored version and explanation."""
        if self._session is None:
            return ("", f"Refactor `{candidate.name}`: {candidate.detail}")

        llm = getattr(self._session, "_llm", None) or getattr(self._session, "llm", None)
        if llm is None:
            return ("", f"Refactor `{candidate.name}`: {candidate.detail}")

        prompt = (
            f"The following Python code has a smell: {candidate.kind.value} — {candidate.detail}\n\n"
            f"```python\n{snippet}\n```\n\n"
            "Provide:\n"
            "1. A refactored version (just the code, no explanation in the code block)\n"
            "2. A one-sentence explanation of the change\n\n"
            "Format:\n"
            "REFACTORED:\n```python\n<code>\n```\n\nEXPLANATION: <one sentence>"
        )

        messages = [
            {"role": "system", "content": "You are an expert Python refactoring assistant."},
            {"role": "user", "content": prompt},
        ]

        try:
            resp = await llm.acompletion(messages=messages, max_tokens=400, temperature=0.2)
            raw = ""
            if hasattr(resp, "choices") and resp.choices:
                raw = resp.choices[0].message.content or ""
            return _parse_llm_refactor(raw, snippet)
        except Exception:
            return ("", f"Refactor `{candidate.name}`: {candidate.detail}")


def _parse_llm_refactor(raw: str, fallback_before: str) -> tuple[str, str]:
    """Parse LLM response into (after_snippet, explanation)."""
    import re

    after = ""
    explanation = ""

    code_match = re.search(r"REFACTORED:\s*```python\s*(.*?)\s*```", raw, re.DOTALL)
    if code_match:
        after = code_match.group(1).strip()

    exp_match = re.search(r"EXPLANATION:\s*(.+)", raw)
    if exp_match:
        explanation = exp_match.group(1).strip()

    return (after, explanation)
