"""System bootstrap with dependency ordering."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass
from typing import Any, Callable


class BootstrapPhase(str, enum.Enum):
    """Ordered phases of system bootstrap."""

    CONFIG = "config"
    DATABASE = "database"
    PLUGINS = "plugins"
    AGENTS = "agents"
    TOOLS = "tools"
    READY = "ready"


@dataclass(frozen=True)
class BootstrapStep:
    """A single bootstrap step."""

    name: str
    phase: BootstrapPhase
    handler: Callable[..., Any] | None = None
    depends_on: tuple[str, ...] = ()
    timeout: float = 30.0


@dataclass(frozen=True)
class BootstrapResult:
    """Result of executing a bootstrap step."""

    step_name: str
    success: bool
    duration_ms: float = 0.0
    error: str = ""


class BootstrapError(Exception):
    """Error during bootstrap execution."""


class BootstrapManager:
    """Manages system bootstrap with dependency ordering."""

    def __init__(self) -> None:
        self._steps: dict[str, BootstrapStep] = {}
        self._results: list[BootstrapResult] = []
        self._completed: set[str] = set()

    def add_step(self, step: BootstrapStep) -> None:
        """Register a bootstrap step."""
        self._steps[step.name] = step

    def run(self) -> list[BootstrapResult]:
        """Run all bootstrap steps in dependency order."""
        self._results.clear()
        self._completed.clear()
        order = self._resolve_order(list(self._steps.values()))
        for step in order:
            self._execute_step(step)
        return list(self._results)

    def run_phase(self, phase: BootstrapPhase) -> list[BootstrapResult]:
        """Run only steps belonging to *phase*."""
        phase_steps = [s for s in self._steps.values() if s.phase == phase]
        order = self._resolve_order(phase_steps)
        results: list[BootstrapResult] = []
        for step in order:
            result = self._execute_step(step)
            results.append(result)
        return results

    def is_ready(self) -> bool:
        """Return True if all steps completed successfully."""
        if not self._results:
            return False
        return all(r.success for r in self._results)

    def health_check(self) -> dict[str, bool]:
        """Return step_name -> success mapping."""
        return {r.step_name: r.success for r in self._results}

    def results(self) -> list[BootstrapResult]:
        """Return all results."""
        return list(self._results)

    def summary(self) -> str:
        """Return a human-readable summary."""
        if not self._results:
            return "No bootstrap steps have been run."
        total = len(self._results)
        passed = sum(1 for r in self._results if r.success)
        failed = total - passed
        lines = [f"Bootstrap: {passed}/{total} steps succeeded."]
        if failed:
            for r in self._results:
                if not r.success:
                    lines.append(f"  FAILED: {r.step_name} — {r.error}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_order(self, steps: list[BootstrapStep]) -> list[BootstrapStep]:
        """Topological sort of steps by depends_on."""
        by_name = {s.name: s for s in steps}
        visited: set[str] = set()
        order: list[BootstrapStep] = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            step = by_name.get(name)
            if step is None:
                return
            for dep in step.depends_on:
                if dep in by_name:
                    visit(dep)
            order.append(step)

        for s in steps:
            visit(s.name)
        return order

    def _execute_step(self, step: BootstrapStep) -> BootstrapResult:
        # Check dependencies
        for dep in step.depends_on:
            if dep not in self._completed:
                result = BootstrapResult(
                    step_name=step.name,
                    success=False,
                    error=f"Dependency '{dep}' not completed.",
                )
                self._results.append(result)
                return result

        start = time.monotonic()
        try:
            if step.handler is not None:
                step.handler()
            elapsed = (time.monotonic() - start) * 1000
            result = BootstrapResult(
                step_name=step.name, success=True, duration_ms=elapsed,
            )
            self._completed.add(step.name)
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            result = BootstrapResult(
                step_name=step.name, success=False,
                duration_ms=elapsed, error=str(exc),
            )
        self._results.append(result)
        return result
