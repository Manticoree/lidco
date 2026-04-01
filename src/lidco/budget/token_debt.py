"""Track token overspend as debt to repay via compaction."""
from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class DebtEntry:
    """A single debt record."""

    amount: int
    reason: str = ""
    timestamp: float = field(default_factory=time.time)
    repaid: int = 0


@dataclass(frozen=True)
class DebtSummary:
    """Aggregate debt statistics."""

    total_debt: int = 0
    total_repaid: int = 0
    outstanding: int = 0
    entries: int = 0
    ceiling: int = 50000


class TokenDebtTracker:
    """Track token overspend as debt to repay via compaction."""

    def __init__(self, ceiling: int = 50000) -> None:
        self._ceiling = ceiling
        self._entries: list[DebtEntry] = []

    def incur(self, amount: int, reason: str = "") -> DebtEntry:
        """Add a new debt entry."""
        entry = DebtEntry(amount=amount, reason=reason)
        self._entries = [*self._entries, entry]
        return entry

    def repay(self, amount: int) -> int:
        """Reduce debt FIFO across entries. Return actual amount repaid."""
        remaining = amount
        actual_repaid = 0
        new_entries: list[DebtEntry] = []

        for entry in self._entries:
            owed = entry.amount - entry.repaid
            if remaining <= 0 or owed <= 0:
                new_entries.append(entry)
                continue
            payment = min(remaining, owed)
            new_entries.append(
                DebtEntry(
                    amount=entry.amount,
                    reason=entry.reason,
                    timestamp=entry.timestamp,
                    repaid=entry.repaid + payment,
                )
            )
            remaining -= payment
            actual_repaid += payment

        self._entries = new_entries
        return actual_repaid

    def outstanding(self) -> int:
        """Total unpaid debt."""
        return sum(e.amount - e.repaid for e in self._entries)

    def is_over_ceiling(self) -> bool:
        """Whether outstanding debt exceeds ceiling."""
        return self.outstanding() > self._ceiling

    def get_debts(self) -> list[DebtEntry]:
        """Return all debt entries."""
        return list(self._entries)

    def get_summary(self) -> DebtSummary:
        """Aggregate debt statistics."""
        total_debt = sum(e.amount for e in self._entries)
        total_repaid = sum(e.repaid for e in self._entries)
        return DebtSummary(
            total_debt=total_debt,
            total_repaid=total_repaid,
            outstanding=total_debt - total_repaid,
            entries=len(self._entries),
            ceiling=self._ceiling,
        )

    def clear(self) -> None:
        """Remove all debt entries."""
        self._entries = []

    def summary(self) -> str:
        """Human-readable debt summary."""
        s = self.get_summary()
        status = "OVER CEILING" if self.is_over_ceiling() else "OK"
        return (
            f"Token debt: {s.outstanding}/{s.ceiling} ({status}), "
            f"{s.entries} entries, {s.total_repaid} repaid"
        )
