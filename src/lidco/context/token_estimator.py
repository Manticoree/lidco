"""Token Estimator — estimate token counts from text using character heuristics.

Stdlib only — no external deps.
"""
from __future__ import annotations

import json


class TokenEstimator:
    """Estimate token counts from text."""

    def __init__(self, chars_per_token: float = 4.0) -> None:
        self._chars_per_token = chars_per_token

    @property
    def chars_per_token(self) -> float:
        return self._chars_per_token

    def estimate(self, text: str) -> int:
        """Estimate tokens in a string."""
        if not text:
            return 0
        return max(1, int(len(text) / self._chars_per_token))

    def estimate_messages(self, messages: list[dict]) -> int:
        """Estimate total tokens across a list of messages."""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.estimate(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        total += self.estimate(part.get("text", ""))
                    elif isinstance(part, str):
                        total += self.estimate(part)
            # Add a small overhead per message for role/metadata
            total += 4
        return total

    def estimate_dict(self, d: object) -> int:
        """Estimate tokens for any nested dict/list/str."""
        if isinstance(d, str):
            return self.estimate(d)
        if isinstance(d, dict):
            total = 0
            for k, v in d.items():
                total += self.estimate(str(k))
                total += self.estimate_dict(v)
            return total
        if isinstance(d, (list, tuple)):
            return sum(self.estimate_dict(item) for item in d)
        # Numbers, bools, None — treat as short string
        return self.estimate(str(d))

    def calibrate(self, samples: list[tuple[str, int]]) -> None:
        """Update chars_per_token from (text, true_token_count) pairs."""
        if not samples:
            return
        total_chars = 0
        total_tokens = 0
        for text, true_count in samples:
            if true_count > 0:
                total_chars += len(text)
                total_tokens += true_count
        if total_tokens > 0:
            self._chars_per_token = total_chars / total_tokens
