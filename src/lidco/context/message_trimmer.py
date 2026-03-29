"""Message Trimmer — trim message lists to fit within a token budget.

Stdlib only — no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.context.token_estimator import TokenEstimator


@dataclass
class TrimResult:
    """Result of a message trim operation."""
    messages: list[dict]
    removed_count: int
    tokens_saved: int


class MessageTrimmer:
    """Trim message lists to stay within a token budget."""

    def __init__(
        self,
        estimator: TokenEstimator | None = None,
        keep_system: bool = True,
        keep_recent: int = 4,
    ) -> None:
        self._estimator = estimator or TokenEstimator()
        self._keep_system = keep_system
        self._keep_recent = keep_recent

    def trim(self, messages: list[dict], budget: int) -> TrimResult:
        """Trim messages to fit within budget tokens.

        Strategy:
        - Always keep system messages if keep_system=True
        - Always keep last keep_recent messages
        - Remove oldest non-system messages until within budget
        """
        if not messages:
            return TrimResult(messages=[], removed_count=0, tokens_saved=0)

        original_tokens = self._estimator.estimate_messages(messages)
        if original_tokens <= budget:
            return TrimResult(
                messages=list(messages),
                removed_count=0,
                tokens_saved=0,
            )

        # Identify protected indices (system + last keep_recent)
        protected: set[int] = set()
        if self._keep_system:
            for i, msg in enumerate(messages):
                if msg.get("role") == "system":
                    protected.add(i)

        last_n = self._keep_recent
        n = len(messages)
        for i in range(max(0, n - last_n), n):
            protected.add(i)

        # Build removal candidates (oldest first, not protected)
        candidates = [i for i in range(n) if i not in protected]

        working = list(messages)
        removed = []
        tokens_saved = 0

        for idx in candidates:
            current_tokens = self._estimator.estimate_messages(working)
            if current_tokens <= budget:
                break
            # Remove message at adjusted index
            adjusted_idx = idx - len(removed)
            if 0 <= adjusted_idx < len(working):
                msg = working[adjusted_idx]
                msg_tokens = self._estimator.estimate_messages([msg])
                tokens_saved += msg_tokens
                working.pop(adjusted_idx)
                removed.append(idx)

        return TrimResult(
            messages=working,
            removed_count=len(removed),
            tokens_saved=tokens_saved,
        )

    def trim_to_ratio(self, messages: list[dict], ratio: float = 0.8) -> TrimResult:
        """Trim messages so total tokens <= ratio * current_total."""
        if not messages:
            return TrimResult(messages=[], removed_count=0, tokens_saved=0)
        total = self._estimator.estimate_messages(messages)
        budget = int(total * ratio)
        return self.trim(messages, budget)
