"""Learn from past error resolutions and suggest fixes."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field


@dataclass
class Resolution:
    """A recorded error resolution."""

    error_pattern: str
    fix_description: str
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0.0


class ErrorPatternLearner:
    """Learn from resolutions and suggest fixes ranked by success rate."""

    def __init__(self) -> None:
        self._resolutions: dict[str, Resolution] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_resolution(
        self, error_pattern: str, fix_description: str, success: bool
    ) -> Resolution:
        """Record an outcome for *error_pattern* + *fix_description*."""
        key = f"{error_pattern}::{fix_description}"
        if key not in self._resolutions:
            self._resolutions[key] = Resolution(
                error_pattern=error_pattern,
                fix_description=fix_description,
            )
        res = self._resolutions[key]
        if success:
            res.success_count += 1
        else:
            res.failure_count += 1
        res.last_used = time.time()
        return res

    def suggest(
        self, error_message: str, limit: int = 5
    ) -> list[Resolution]:
        """Return matching resolutions ranked by success rate."""
        matches: list[Resolution] = []
        for res in self._resolutions.values():
            if re.search(re.escape(res.error_pattern), error_message, re.IGNORECASE):
                matches.append(res)
        matches.sort(key=lambda r: self._rate(r), reverse=True)
        return matches[:limit]

    def best_fix(self, error_message: str) -> Resolution | None:
        """Return the single best resolution or ``None``."""
        suggestions = self.suggest(error_message, limit=1)
        return suggestions[0] if suggestions else None

    def success_rate(self, error_pattern: str) -> float:
        """Return aggregate success rate for *error_pattern*."""
        total_s = 0
        total_f = 0
        for res in self._resolutions.values():
            if res.error_pattern == error_pattern:
                total_s += res.success_count
                total_f += res.failure_count
        total = total_s + total_f
        return total_s / total if total else 0.0

    def all_resolutions(self) -> list[Resolution]:
        """Return all recorded resolutions."""
        return list(self._resolutions.values())

    def top_fixes(self, limit: int = 10) -> list[Resolution]:
        """Return top resolutions by success rate."""
        items = list(self._resolutions.values())
        items.sort(key=lambda r: self._rate(r), reverse=True)
        return items[:limit]

    def summary(self) -> dict:
        """Return summary statistics."""
        total_s = sum(r.success_count for r in self._resolutions.values())
        total_f = sum(r.failure_count for r in self._resolutions.values())
        total = total_s + total_f
        return {
            "resolution_count": len(self._resolutions),
            "total_attempts": total,
            "overall_success_rate": total_s / total if total else 0.0,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _rate(res: Resolution) -> float:
        total = res.success_count + res.failure_count
        return res.success_count / total if total else 0.0
