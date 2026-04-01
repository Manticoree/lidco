"""Phase definitions for the 7-phase feature development workflow.

Phases: DISCOVERY -> EXPLORATION -> CLARIFICATION -> ARCHITECTURE ->
        IMPLEMENTATION -> REVIEW -> SUMMARY
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Phase(str, Enum):
    """The seven phases of feature development."""

    DISCOVERY = "discovery"
    EXPLORATION = "exploration"
    CLARIFICATION = "clarification"
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    SUMMARY = "summary"


class PhaseStatus(str, Enum):
    """Status of a single phase."""

    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class PhaseResult:
    """Immutable result of executing a single phase."""

    phase: Phase
    status: PhaseStatus
    output: str
    duration_ms: int


@dataclass(frozen=True)
class PhaseConfig:
    """Immutable configuration for a single phase."""

    max_agents: int
    timeout_s: float
    required: bool


# Ordered tuple of all phases in execution order.
PHASE_ORDER: tuple[Phase, ...] = tuple(Phase)

DEFAULT_CONFIGS: dict[Phase, PhaseConfig] = {
    Phase.DISCOVERY: PhaseConfig(max_agents=1, timeout_s=30.0, required=True),
    Phase.EXPLORATION: PhaseConfig(max_agents=2, timeout_s=60.0, required=True),
    Phase.CLARIFICATION: PhaseConfig(max_agents=1, timeout_s=30.0, required=False),
    Phase.ARCHITECTURE: PhaseConfig(max_agents=2, timeout_s=60.0, required=True),
    Phase.IMPLEMENTATION: PhaseConfig(max_agents=3, timeout_s=120.0, required=True),
    Phase.REVIEW: PhaseConfig(max_agents=2, timeout_s=60.0, required=True),
    Phase.SUMMARY: PhaseConfig(max_agents=1, timeout_s=30.0, required=True),
}


__all__ = [
    "Phase",
    "PhaseStatus",
    "PhaseResult",
    "PhaseConfig",
    "PHASE_ORDER",
    "DEFAULT_CONFIGS",
]
