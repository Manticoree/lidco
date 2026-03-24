"""AtMentionMiddleware — pre-process @-mentions in user input before LLM call."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.context.at_mention import AtMentionParser, AtMentionResult


@dataclass
class ProcessedInput:
    clean_text: str
    injected_context: list[AtMentionResult]
    total_tokens: int
    errors: list[str] = field(default_factory=list)


class AtMentionMiddleware:
    """Resolve @-mentions in user input and inject them as context."""

    def __init__(
        self,
        parser: AtMentionParser,
        max_tokens: int = 4096,
    ) -> None:
        self._parser = parser
        self._max_tokens = max_tokens

    def process(self, user_input: str) -> ProcessedInput:
        """Resolve all @-mentions; enforce token budget; return ProcessedInput."""
        try:
            clean_text, results = self._parser.resolve(user_input)
        except Exception as exc:
            return ProcessedInput(
                clean_text=user_input,
                injected_context=[],
                total_tokens=0,
                errors=[str(exc)],
            )

        errors: list[str] = []
        kept: list[AtMentionResult] = []
        total = 0

        for r in results:
            if r.error:
                errors.append(f"@{r.provider} {r.identifier}: {r.error}")
                continue
            if total + r.token_estimate <= self._max_tokens:
                kept.append(r)
                total += r.token_estimate
            # Drop if over budget (lowest-priority = later in list)

        return ProcessedInput(
            clean_text=clean_text,
            injected_context=kept,
            total_tokens=total,
            errors=errors,
        )
