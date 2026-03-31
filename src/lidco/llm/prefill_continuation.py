"""Prefill Continuation Engine — detect truncated LLM output and auto-continue."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


_DEFAULT_TRUNCATION_MARKERS: list[str] = [
    "...",
    "# continued",
    "// continued",
    "/* continued",
]

# Patterns that indicate code was cut mid-block (no closing delimiter on last line).
_OPEN_DELIMITERS = {"(", "{", "["}
_CLOSE_DELIMITERS = {")", "}", "]"}


@dataclass
class ContinuationResult:
    """Result of a prefill continuation loop."""

    full_text: str
    continuations: int
    truncated: bool
    total_tokens: int


class PrefillContinuationEngine:
    """Generate, detect truncation, and seamlessly continue LLM output."""

    def __init__(
        self,
        max_continuations: int = 5,
        truncation_markers: list[str] | None = None,
    ) -> None:
        self.max_continuations = max_continuations
        self.truncation_markers: list[str] = (
            list(truncation_markers) if truncation_markers is not None else list(_DEFAULT_TRUNCATION_MARKERS)
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def is_truncated(self, text: str) -> bool:
        """Return *True* if *text* appears to have been cut short."""
        if not text or not text.strip():
            return False

        stripped = text.rstrip()
        last_line = stripped.rsplit("\n", 1)[-1].strip()

        # Explicit markers
        for marker in self.truncation_markers:
            if last_line.endswith(marker):
                return True

        # Unbalanced delimiters in last line → mid-code truncation
        opens = sum(1 for ch in last_line if ch in _OPEN_DELIMITERS)
        closes = sum(1 for ch in last_line if ch in _CLOSE_DELIMITERS)
        if opens > closes:
            return True

        # Overall unbalanced delimiters across entire text
        total_opens = sum(1 for ch in stripped if ch in _OPEN_DELIMITERS)
        total_closes = sum(1 for ch in stripped if ch in _CLOSE_DELIMITERS)
        if total_opens > total_closes:
            return True

        return False

    def build_continuation_prompt(self, original_prompt: str, partial_response: str) -> str:
        """Build a continuation prompt that includes the partial response as prefill."""
        return (
            f"{original_prompt}\n\n"
            "Continue exactly where you left off. Do not repeat any text already produced.\n\n"
            f"--- partial response so far ---\n{partial_response}\n--- end partial ---"
        )

    def merge_responses(self, responses: list[str]) -> str:
        """Merge a sequence of continuation responses, removing overlapping text."""
        if not responses:
            return ""
        if len(responses) == 1:
            return responses[0]

        merged = responses[0]
        for part in responses[1:]:
            overlap = self._find_overlap(merged, part)
            if overlap > 0:
                merged += part[overlap:]
            else:
                merged += part
        return merged

    def process(self, generate_fn: Callable[[str], str], prompt: str) -> ContinuationResult:
        """Full continuation loop: generate → check → continue until complete or max."""
        responses: list[str] = []
        current_prompt = prompt
        continuations = 0
        total_tokens = 0

        response = generate_fn(current_prompt)
        responses.append(response)
        total_tokens += len(response.split())  # rough token estimate

        while continuations < self.max_continuations:
            merged_so_far = self.merge_responses(responses)
            if not self.is_truncated(merged_so_far):
                break
            continuations += 1
            current_prompt = self.build_continuation_prompt(prompt, merged_so_far)
            response = generate_fn(current_prompt)
            responses.append(response)
            total_tokens += len(response.split())

        full_text = self.merge_responses(responses)
        still_truncated = self.is_truncated(full_text)

        return ContinuationResult(
            full_text=full_text,
            continuations=continuations,
            truncated=still_truncated,
            total_tokens=total_tokens,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _find_overlap(a: str, b: str) -> int:
        """Find the length of the longest suffix of *a* that is a prefix of *b*."""
        max_overlap = min(len(a), len(b))
        for size in range(max_overlap, 0, -1):
            if a.endswith(b[:size]):
                return size
        return 0
