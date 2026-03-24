"""Long-horizon task planner with retry/resume (Replit Agent 3 / Devin parity).

Breaks a high-level goal into phases, each consisting of atomic steps.
Supports:
- Checkpoint persistence (JSON) for resume-after-crash
- Per-step retry with exponential back-off
- Phase-level rollback callbacks
- Human confirmation gates between phases (optional)
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Awaitable


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class PlanStep:
    id: str
    description: str
    phase: str
    status: StepStatus = StepStatus.PENDING
    result: str = ""
    error: str = ""
    attempts: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0


@dataclass
class PlanPhase:
    name: str
    steps: list[PlanStep] = field(default_factory=list)
    status: PhaseStatus = PhaseStatus.PENDING
    rollback_done: bool = False

    def is_complete(self) -> bool:
        return all(s.status in (StepStatus.DONE, StepStatus.SKIPPED) for s in self.steps)

    def has_failures(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)


@dataclass
class HorizonResult:
    goal: str
    phases_total: int
    phases_done: int
    steps_total: int
    steps_done: int
    steps_failed: int
    success: bool
    resumed: bool = False
    elapsed: float = 0.0


StepRunner = Callable[[PlanStep], Awaitable[str]]
RollbackFn = Callable[[PlanPhase], Awaitable[None]]
ConfirmFn = Callable[[PlanPhase], Awaitable[bool]]


class HorizonPlanner:
    """Long-horizon task executor with checkpointing and retry.

    Parameters
    ----------
    step_runner:
        Async callable that executes a single step.  Returns a result string.
        Raise an exception to signal failure.
    rollback_fn:
        Optional async callable invoked when a phase fails.
    confirm_fn:
        Optional async callable invoked before each phase starts.
        Return False to abort the run.
    checkpoint_path:
        JSON file to persist progress.  If None, no persistence.
    max_retries:
        How many times to retry a failed step before marking it FAILED.
    backoff_base:
        Initial wait (seconds) before first retry; doubles each attempt.
    """

    def __init__(
        self,
        step_runner: StepRunner | None = None,
        rollback_fn: RollbackFn | None = None,
        confirm_fn: ConfirmFn | None = None,
        checkpoint_path: str | Path | None = None,
        max_retries: int = 2,
        backoff_base: float = 1.0,
    ) -> None:
        self._runner = step_runner
        self._rollback = rollback_fn
        self._confirm = confirm_fn
        self._ckpt = Path(checkpoint_path) if checkpoint_path else None
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._phases: list[PlanPhase] = []
        self._goal: str = ""

    # ------------------------------------------------------------------
    # Plan construction
    # ------------------------------------------------------------------

    def set_goal(self, goal: str) -> None:
        self._goal = goal

    def add_phase(self, name: str, steps: list[tuple[str, str]]) -> PlanPhase:
        """Add a phase with (step_id, description) tuples."""
        plan_steps = [PlanStep(id=sid, description=desc, phase=name) for sid, desc in steps]
        phase = PlanPhase(name=name, steps=plan_steps)
        self._phases.append(phase)
        return phase

    def format_plan(self) -> str:
        lines: list[str] = [f"Goal: {self._goal}", ""]
        for i, phase in enumerate(self._phases, 1):
            lines.append(f"Phase {i}: {phase.name}")
            for step in phase.steps:
                icon = {"pending": "○", "running": "◉", "done": "✓", "failed": "✗", "skipped": "–"}.get(step.status, "○")
                lines.append(f"  {icon} [{step.id}] {step.description}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(self, resume: bool = False) -> HorizonResult:
        start = time.time()
        resumed = False

        if resume and self._ckpt and self._ckpt.exists():
            self._load_checkpoint()
            resumed = True

        for phase in self._phases:
            if phase.status == PhaseStatus.DONE:
                continue  # already completed in previous run

            # Confirmation gate
            if self._confirm is not None:
                approved = await self._confirm(phase)
                if not approved:
                    phase.status = PhaseStatus.FAILED
                    break

            phase.status = PhaseStatus.RUNNING
            self._save_checkpoint()

            for step in phase.steps:
                if step.status in (StepStatus.DONE, StepStatus.SKIPPED):
                    continue
                await self._run_step_with_retry(step)
                self._save_checkpoint()

            if phase.has_failures():
                phase.status = PhaseStatus.FAILED
                if self._rollback is not None:
                    await self._rollback(phase)
                    phase.rollback_done = True
                    phase.status = PhaseStatus.ROLLED_BACK
                self._save_checkpoint()
                break
            else:
                phase.status = PhaseStatus.DONE
                self._save_checkpoint()

        return self._build_result(start, resumed)

    async def _run_step_with_retry(self, step: PlanStep) -> None:
        step.status = StepStatus.RUNNING
        step.started_at = time.time()

        for attempt in range(self.max_retries + 1):
            step.attempts = attempt + 1
            try:
                if self._runner is None:
                    result = f"[no runner] step {step.id} simulated"
                else:
                    result = await self._runner(step)
                step.result = result
                step.status = StepStatus.DONE
                step.finished_at = time.time()
                return
            except Exception as exc:
                step.error = str(exc)
                if attempt < self.max_retries:
                    wait = self.backoff_base * (2 ** attempt)
                    await asyncio.sleep(wait)

        step.status = StepStatus.FAILED
        step.finished_at = time.time()

    # ------------------------------------------------------------------
    # Checkpoint
    # ------------------------------------------------------------------

    def _save_checkpoint(self) -> None:
        if not self._ckpt:
            return
        self._ckpt.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "goal": self._goal,
            "phases": [
                {
                    "name": p.name,
                    "status": p.status,
                    "rollback_done": p.rollback_done,
                    "steps": [asdict(s) for s in p.steps],
                }
                for p in self._phases
            ],
        }
        self._ckpt.write_text(json.dumps(data, indent=2))

    def _load_checkpoint(self) -> None:
        data = json.loads(self._ckpt.read_text())  # type: ignore[union-attr]
        self._goal = data.get("goal", self._goal)
        phase_map = {p.name: p for p in self._phases}
        for pd in data.get("phases", []):
            phase = phase_map.get(pd["name"])
            if not phase:
                continue
            phase.status = PhaseStatus(pd["status"])
            phase.rollback_done = pd.get("rollback_done", False)
            step_map = {s.id: s for s in phase.steps}
            for sd in pd.get("steps", []):
                step = step_map.get(sd["id"])
                if step:
                    step.status = StepStatus(sd["status"])
                    step.result = sd.get("result", "")
                    step.error = sd.get("error", "")
                    step.attempts = sd.get("attempts", 0)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def _build_result(self, start: float, resumed: bool) -> HorizonResult:
        all_steps = [s for p in self._phases for s in p.steps]
        done_phases = sum(1 for p in self._phases if p.status == PhaseStatus.DONE)
        return HorizonResult(
            goal=self._goal,
            phases_total=len(self._phases),
            phases_done=done_phases,
            steps_total=len(all_steps),
            steps_done=sum(1 for s in all_steps if s.status == StepStatus.DONE),
            steps_failed=sum(1 for s in all_steps if s.status == StepStatus.FAILED),
            success=(done_phases == len(self._phases)),
            resumed=resumed,
            elapsed=time.time() - start,
        )
