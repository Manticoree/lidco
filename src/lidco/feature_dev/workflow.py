"""Feature Development Workflow — orchestrates 7 phases end-to-end.

Usage::

    wf = FeatureDevWorkflow("my-feature", "Add caching layer")
    result = wf.run_phase(Phase.DISCOVERY)
    all_results = wf.run_all()
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from lidco.feature_dev.phases import (
    DEFAULT_CONFIGS,
    PHASE_ORDER,
    Phase,
    PhaseConfig,
    PhaseResult,
    PhaseStatus,
)


class WorkflowError(Exception):
    """Raised when workflow execution fails."""


@dataclass(frozen=True)
class _WorkflowState:
    """Internal immutable snapshot of workflow progress."""

    results: tuple[PhaseResult, ...] = ()
    skipped: frozenset[Phase] = frozenset()
    phase_index: int = 0


class FeatureDevWorkflow:
    """Orchestrates the 7-phase feature development workflow.

    Immutable-style: ``skip_phase`` returns a new workflow instance.
    Phase handlers are simple stubs that return descriptive output;
    subclasses or composition can override them with real logic.
    """

    def __init__(
        self,
        name: str,
        description: str,
        *,
        configs: dict[Phase, PhaseConfig] | None = None,
    ) -> None:
        if not name.strip():
            raise WorkflowError("Workflow name must not be empty")
        self._name = name
        self._description = description
        self._configs: dict[Phase, PhaseConfig] = {
            **DEFAULT_CONFIGS,
            **(configs or {}),
        }
        self._state = _WorkflowState()

    # ------------------------------------------------------------------ #
    # Public read-only properties                                         #
    # ------------------------------------------------------------------ #

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def current_phase(self) -> Phase:
        idx = self._state.phase_index
        if idx >= len(PHASE_ORDER):
            return PHASE_ORDER[-1]
        return PHASE_ORDER[idx]

    @property
    def history(self) -> tuple[PhaseResult, ...]:
        return self._state.results

    @property
    def is_complete(self) -> bool:
        return self._state.phase_index >= len(PHASE_ORDER)

    # ------------------------------------------------------------------ #
    # Execution                                                           #
    # ------------------------------------------------------------------ #

    def run_phase(self, phase: Phase) -> PhaseResult:
        """Execute a single phase and record the result."""
        if phase in self._state.skipped:
            result = PhaseResult(
                phase=phase,
                status=PhaseStatus.SKIPPED,
                output=f"Phase {phase.value} was skipped",
                duration_ms=0,
            )
            self._state = _WorkflowState(
                results=(*self._state.results, result),
                skipped=self._state.skipped,
                phase_index=self._state.phase_index + 1,
            )
            return result

        handler = self._phase_handler(phase)
        start = time.monotonic()
        try:
            output = handler()
            elapsed = int((time.monotonic() - start) * 1000)
            result = PhaseResult(
                phase=phase,
                status=PhaseStatus.DONE,
                output=output,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            result = PhaseResult(
                phase=phase,
                status=PhaseStatus.DONE,
                output=f"Error: {exc}",
                duration_ms=elapsed,
            )

        self._state = _WorkflowState(
            results=(*self._state.results, result),
            skipped=self._state.skipped,
            phase_index=self._state.phase_index + 1,
        )
        return result

    def run_all(self) -> tuple[PhaseResult, ...]:
        """Execute all remaining phases in order."""
        results: list[PhaseResult] = []
        for phase in PHASE_ORDER:
            if self._already_ran(phase):
                continue
            results.append(self.run_phase(phase))
        return tuple(results)

    def skip_phase(self, phase: Phase) -> FeatureDevWorkflow:
        """Return a new workflow with *phase* marked as skipped."""
        new_wf = FeatureDevWorkflow(
            self._name,
            self._description,
            configs=dict(self._configs),
        )
        new_wf._state = _WorkflowState(
            results=self._state.results,
            skipped=self._state.skipped | {phase},
            phase_index=self._state.phase_index,
        )
        return new_wf

    # ------------------------------------------------------------------ #
    # Phase handlers                                                      #
    # ------------------------------------------------------------------ #

    def _phase_handler(self, phase: Phase):  # noqa: ANN202
        handlers = {
            Phase.DISCOVERY: self._discover,
            Phase.EXPLORATION: self._explore,
            Phase.CLARIFICATION: self._clarify,
            Phase.ARCHITECTURE: self._architect,
            Phase.IMPLEMENTATION: self._implement,
            Phase.REVIEW: self._review,
            Phase.SUMMARY: self._summarize,
        }
        return handlers[phase]

    def _discover(self) -> str:
        return f"Discovered requirements for '{self._name}': {self._description}"

    def _explore(self) -> str:
        return f"Explored codebase for patterns related to '{self._name}'"

    def _clarify(self) -> str:
        return f"Clarified requirements and constraints for '{self._name}'"

    def _architect(self) -> str:
        return f"Designed architecture for '{self._name}'"

    def _implement(self) -> str:
        return f"Implemented '{self._name}' according to architecture"

    def _review(self) -> str:
        return f"Reviewed implementation of '{self._name}'"

    def _summarize(self) -> str:
        done = sum(1 for r in self._state.results if r.status == PhaseStatus.DONE)
        skipped = sum(1 for r in self._state.results if r.status == PhaseStatus.SKIPPED)
        return (
            f"Feature '{self._name}' complete: "
            f"{done} phases done, {skipped} skipped"
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _already_ran(self, phase: Phase) -> bool:
        return any(r.phase == phase for r in self._state.results)


__all__ = [
    "FeatureDevWorkflow",
    "WorkflowError",
]
