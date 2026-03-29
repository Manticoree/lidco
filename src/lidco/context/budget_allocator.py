"""Budget Allocator — proportional token budget allocation across named slots.

Stdlib only — no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BudgetSlot:
    """A named slot with weight and optional min/max token constraints."""
    name: str
    weight: float
    min_tokens: int = 0
    max_tokens: int = 0  # 0 means no upper limit


@dataclass
class AllocationPlan:
    """Result of a budget allocation computation."""
    total: int
    slots: dict[str, int] = field(default_factory=dict)
    overflow: bool = False


class BudgetAllocator:
    """Allocate a total token budget proportionally across named slots."""

    def __init__(self, total_budget: int) -> None:
        self._total = total_budget
        self._slots: dict[str, BudgetSlot] = {}

    def add_slot(self, slot: BudgetSlot) -> None:
        """Add or update a budget slot."""
        self._slots[slot.name] = slot

    def remove_slot(self, name: str) -> None:
        """Remove a slot by name."""
        self._slots.pop(name, None)

    def set_total(self, total: int) -> None:
        """Update the total budget."""
        self._total = total

    def allocate(self) -> AllocationPlan:
        """Compute proportional allocation respecting min/max constraints."""
        if not self._slots:
            return AllocationPlan(total=self._total, slots={}, overflow=False)

        total_weight = sum(s.weight for s in self._slots.values())
        if total_weight <= 0:
            # Equal distribution
            per = self._total // len(self._slots)
            return AllocationPlan(
                total=self._total,
                slots={name: per for name in self._slots},
                overflow=False,
            )

        # First pass: proportional allocation
        raw: dict[str, float] = {}
        for name, slot in self._slots.items():
            raw[name] = (slot.weight / total_weight) * self._total

        # Second pass: enforce min/max, collect overflow
        allocated: dict[str, int] = {}
        remaining = self._total
        overflow = False

        # Clamp to min first
        for name, slot in self._slots.items():
            val = int(raw[name])
            if slot.min_tokens > 0 and val < slot.min_tokens:
                val = slot.min_tokens
            allocated[name] = val
            remaining -= val

        # Clamp to max; redistribute excess
        for name, slot in self._slots.items():
            if slot.max_tokens > 0 and allocated[name] > slot.max_tokens:
                excess = allocated[name] - slot.max_tokens
                allocated[name] = slot.max_tokens
                remaining += excess

        # Detect overflow (mins exceed total)
        if remaining < 0:
            overflow = True

        return AllocationPlan(total=self._total, slots=allocated, overflow=overflow)
