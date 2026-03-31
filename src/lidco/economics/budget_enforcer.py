"""Budget Enforcer — session/daily/monthly budgets with soft warn and hard stop."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class BudgetLimit:
    """A budget limit definition."""

    name: str
    limit_dollars: float
    warn_threshold: float = 0.8  # fraction at which soft warning fires
    hard_stop: bool = True       # whether to block at 100%


@dataclass
class BudgetUsage:
    """Tracks spending against a budget limit."""

    budget: BudgetLimit
    spent_dollars: float = 0.0
    last_updated: float = field(default_factory=time.time)

    @property
    def fraction(self) -> float:
        if self.budget.limit_dollars <= 0:
            return 1.0
        return self.spent_dollars / self.budget.limit_dollars

    @property
    def remaining(self) -> float:
        return max(0.0, self.budget.limit_dollars - self.spent_dollars)

    @property
    def is_warning(self) -> bool:
        return self.fraction >= self.budget.warn_threshold and self.fraction < 1.0

    @property
    def is_exceeded(self) -> bool:
        return self.fraction >= 1.0


@dataclass(frozen=True)
class BudgetEvent:
    """Emitted when a budget threshold is crossed."""

    budget_name: str
    event_type: str  # "warning" | "exceeded" | "record"
    spent: float
    limit: float
    fraction: float
    timestamp: float = field(default_factory=time.time)


class BudgetEnforcer:
    """Manages session, daily, and monthly budgets.

    Soft warn at 80% (configurable), hard stop at 100%.
    Persists state to a JSON file for cross-session tracking.
    """

    def __init__(self, persist_path: str | Path | None = None) -> None:
        self._budgets: dict[str, BudgetUsage] = {}
        self._listeners: list[Callable[[BudgetEvent], None]] = []
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path and self._persist_path.exists():
            self._load()

    # -- Budget management --

    def add_budget(self, budget: BudgetLimit) -> None:
        """Register a new budget limit."""
        self._budgets[budget.name] = BudgetUsage(budget=budget)
        self._save()

    def remove_budget(self, name: str) -> bool:
        """Remove a budget by name. Returns True if removed."""
        if name in self._budgets:
            del self._budgets[name]
            self._save()
            return True
        return False

    def get_budget(self, name: str) -> BudgetUsage | None:
        """Get usage info for a named budget."""
        return self._budgets.get(name)

    def list_budgets(self) -> list[BudgetUsage]:
        """Return all tracked budgets."""
        return list(self._budgets.values())

    # -- Spending --

    def record_spend(self, amount: float, budget_names: list[str] | None = None) -> list[BudgetEvent]:
        """Record spending against specified budgets (or all if None).

        Returns list of events (warnings/exceeded).
        Raises BudgetExceededError if hard_stop budget is exceeded.
        """
        targets = budget_names or list(self._budgets.keys())
        events: list[BudgetEvent] = []
        for name in targets:
            usage = self._budgets.get(name)
            if usage is None:
                continue
            was_warning = usage.is_warning
            was_exceeded = usage.is_exceeded
            usage.spent_dollars += amount
            usage.last_updated = time.time()

            evt = BudgetEvent(
                budget_name=name,
                event_type="record",
                spent=usage.spent_dollars,
                limit=usage.budget.limit_dollars,
                fraction=usage.fraction,
            )
            events.append(evt)
            self._notify(evt)

            if usage.is_exceeded and not was_exceeded:
                exceeded_evt = BudgetEvent(
                    budget_name=name,
                    event_type="exceeded",
                    spent=usage.spent_dollars,
                    limit=usage.budget.limit_dollars,
                    fraction=usage.fraction,
                )
                events.append(exceeded_evt)
                self._notify(exceeded_evt)
                if usage.budget.hard_stop:
                    self._save()
                    raise BudgetExceededError(name, usage.spent_dollars, usage.budget.limit_dollars)
            elif usage.is_warning and not was_warning:
                warn_evt = BudgetEvent(
                    budget_name=name,
                    event_type="warning",
                    spent=usage.spent_dollars,
                    limit=usage.budget.limit_dollars,
                    fraction=usage.fraction,
                )
                events.append(warn_evt)
                self._notify(warn_evt)

        self._save()
        return events

    def check_allowed(self, amount: float, budget_names: list[str] | None = None) -> bool:
        """Check if spending amount would be allowed (not exceed hard-stop budgets)."""
        targets = budget_names or list(self._budgets.keys())
        for name in targets:
            usage = self._budgets.get(name)
            if usage is None:
                continue
            if usage.budget.hard_stop:
                projected = usage.spent_dollars + amount
                if projected > usage.budget.limit_dollars:
                    return False
        return True

    def reset_budget(self, name: str) -> bool:
        """Reset spending for a budget to zero."""
        usage = self._budgets.get(name)
        if usage is None:
            return False
        usage.spent_dollars = 0.0
        usage.last_updated = time.time()
        self._save()
        return True

    # -- Listeners --

    def add_listener(self, callback: Callable[[BudgetEvent], None]) -> None:
        """Register a callback for budget events."""
        self._listeners.append(callback)

    def _notify(self, event: BudgetEvent) -> None:
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass

    # -- Persistence --

    def _save(self) -> None:
        if self._persist_path is None:
            return
        data: dict[str, Any] = {}
        for name, usage in self._budgets.items():
            data[name] = {
                "limit_dollars": usage.budget.limit_dollars,
                "warn_threshold": usage.budget.warn_threshold,
                "hard_stop": usage.budget.hard_stop,
                "spent_dollars": usage.spent_dollars,
                "last_updated": usage.last_updated,
            }
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._persist_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        if self._persist_path is None or not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text())
            for name, info in data.items():
                budget = BudgetLimit(
                    name=name,
                    limit_dollars=info["limit_dollars"],
                    warn_threshold=info.get("warn_threshold", 0.8),
                    hard_stop=info.get("hard_stop", True),
                )
                usage = BudgetUsage(budget=budget, spent_dollars=info.get("spent_dollars", 0.0))
                usage.last_updated = info.get("last_updated", time.time())
                self._budgets[name] = usage
        except (json.JSONDecodeError, KeyError):
            pass

    def summary(self) -> str:
        """Return a human-readable summary of all budgets."""
        if not self._budgets:
            return "No budgets configured."
        lines = ["Budget Status:"]
        for name, usage in self._budgets.items():
            pct = usage.fraction * 100
            status = "EXCEEDED" if usage.is_exceeded else ("WARNING" if usage.is_warning else "OK")
            lines.append(
                f"  {name}: ${usage.spent_dollars:.4f} / ${usage.budget.limit_dollars:.2f} "
                f"({pct:.1f}%) [{status}]"
            )
        return "\n".join(lines)


class BudgetExceededError(Exception):
    """Raised when a hard-stop budget is exceeded."""

    def __init__(self, budget_name: str, spent: float, limit: float) -> None:
        self.budget_name = budget_name
        self.spent = spent
        self.limit = limit
        super().__init__(f"Budget '{budget_name}' exceeded: ${spent:.4f} > ${limit:.2f}")
