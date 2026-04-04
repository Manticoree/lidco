"""Recovery strategies with retry, fix, skip, escalate actions."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RecoveryAction:
    """A single recovery action."""

    type: str  # retry / fix_retry / skip / escalate
    description: str
    max_attempts: int = 3
    backoff_seconds: float = 1.0


@dataclass
class RecoveryChain:
    """Ordered list of actions for a given error type."""

    error_type: str
    actions: list[RecoveryAction] = field(default_factory=list)


def _default_chains() -> dict[str, RecoveryChain]:
    return {
        "syntax": RecoveryChain(
            "syntax",
            [
                RecoveryAction("fix_retry", "Auto-fix syntax and retry", 2, 0.5),
                RecoveryAction("escalate", "Escalate to user for manual fix"),
            ],
        ),
        "runtime": RecoveryChain(
            "runtime",
            [
                RecoveryAction("retry", "Retry the operation", 3, 1.0),
                RecoveryAction("fix_retry", "Attempt automatic fix and retry", 2, 1.0),
                RecoveryAction("escalate", "Escalate to user"),
            ],
        ),
        "network": RecoveryChain(
            "network",
            [
                RecoveryAction("retry", "Retry with backoff", 5, 2.0),
                RecoveryAction("skip", "Skip network operation"),
                RecoveryAction("escalate", "Escalate connectivity issue"),
            ],
        ),
        "permission": RecoveryChain(
            "permission",
            [
                RecoveryAction("fix_retry", "Attempt permission fix and retry", 1, 0.5),
                RecoveryAction("escalate", "Escalate permission issue to user"),
            ],
        ),
        "resource": RecoveryChain(
            "resource",
            [
                RecoveryAction("retry", "Wait and retry", 3, 5.0),
                RecoveryAction("skip", "Skip resource-heavy operation"),
                RecoveryAction("escalate", "Escalate resource exhaustion"),
            ],
        ),
        "timeout": RecoveryChain(
            "timeout",
            [
                RecoveryAction("retry", "Retry with longer timeout", 3, 2.0),
                RecoveryAction("skip", "Skip timed-out operation"),
                RecoveryAction("escalate", "Escalate timeout issue"),
            ],
        ),
        "unknown": RecoveryChain(
            "unknown",
            [
                RecoveryAction("retry", "Generic retry", 2, 1.0),
                RecoveryAction("escalate", "Escalate unknown error"),
            ],
        ),
    }


class RecoveryStrategy:
    """Manage recovery chains per error type."""

    def __init__(self) -> None:
        self._chains: dict[str, RecoveryChain] = _default_chains()

    def get_chain(self, error_type: str) -> RecoveryChain:
        """Return the chain for *error_type*, falling back to 'unknown'."""
        return self._chains.get(error_type, self._chains["unknown"])

    def add_chain(self, chain: RecoveryChain) -> RecoveryChain:
        """Register or replace a recovery chain."""
        self._chains[chain.error_type] = chain
        return chain

    def next_action(
        self, error_type: str, attempt: int
    ) -> RecoveryAction | None:
        """Return the action for *attempt* (0-based) or ``None`` if exhausted."""
        chain = self.get_chain(error_type)
        if attempt < 0:
            return None
        idx = 0
        remaining = attempt
        for action in chain.actions:
            if remaining < action.max_attempts:
                return action
            remaining -= action.max_attempts
        return None

    def all_chains(self) -> list[RecoveryChain]:
        """Return all registered chains."""
        return list(self._chains.values())

    def summary(self) -> dict:
        """Return summary statistics."""
        return {
            "chain_count": len(self._chains),
            "error_types": list(self._chains.keys()),
            "total_actions": sum(
                len(c.actions) for c in self._chains.values()
            ),
        }
