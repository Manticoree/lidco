"""Autonomous loop runner with completion promises (task 1053)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from lidco.autonomous.loop_config import IterationResult, LoopConfig, LoopState


@dataclass(frozen=True)
class LoopResult:
    """Immutable result of an autonomous loop run."""

    config: LoopConfig
    iterations: tuple[IterationResult, ...]
    state: LoopState
    total_duration_ms: int
    completed_naturally: bool


class AutonomousLoopRunner:
    """Repeatedly calls an executor until a completion promise is satisfied.

    Parameters
    ----------
    config:
        Immutable loop configuration.
    """

    def __init__(self, config: LoopConfig) -> None:
        self._config = config
        self._state = LoopState.IDLE
        self._iterations: list[IterationResult] = []
        self._cancel_requested = False
        self._pause_requested = False

    # -- public properties ------------------------------------------------

    @property
    def state(self) -> LoopState:
        return self._state

    @property
    def iterations(self) -> tuple[IterationResult, ...]:
        return tuple(self._iterations)

    # -- control ----------------------------------------------------------

    def pause(self) -> None:
        """Request that the loop pauses after the current iteration."""
        if self._state == LoopState.RUNNING:
            self._pause_requested = True

    def resume(self) -> None:
        """Resume a paused loop (only meaningful when called from another thread)."""
        if self._state == LoopState.PAUSED:
            self._pause_requested = False
            self._state = LoopState.RUNNING

    def cancel(self) -> None:
        """Request loop cancellation."""
        self._cancel_requested = True

    # -- main loop --------------------------------------------------------

    def run(self, executor: Callable[[str, int], str]) -> LoopResult:
        """Execute the autonomous loop.

        *executor* is called as ``executor(prompt, iteration_number)`` where
        *iteration_number* starts at 1.
        """
        self._state = LoopState.RUNNING
        self._iterations = []
        self._cancel_requested = False
        self._pause_requested = False

        start = time.monotonic()
        completed_naturally = False

        try:
            for i in range(1, self._config.max_iterations + 1):
                # -- check cancel / pause --
                if self._cancel_requested:
                    self._state = LoopState.FAILED
                    break

                if self._pause_requested:
                    self._state = LoopState.PAUSED
                    break

                # -- check timeout --
                if self._config.timeout_s is not None:
                    elapsed = time.monotonic() - start
                    if elapsed >= self._config.timeout_s:
                        self._state = LoopState.TIMEOUT
                        break

                # -- execute --
                iter_start = time.monotonic()
                try:
                    output = executor(self._config.prompt, i)
                except Exception as exc:
                    output = f"ERROR: {exc}"
                    self._state = LoopState.FAILED
                    iter_ms = int((time.monotonic() - iter_start) * 1000)
                    self._iterations.append(
                        IterationResult(
                            iteration=i,
                            output=output,
                            duration_ms=iter_ms,
                            claimed_complete=False,
                        )
                    )
                    break

                iter_ms = int((time.monotonic() - iter_start) * 1000)

                claimed = self._check_claimed_complete(output)
                self._iterations.append(
                    IterationResult(
                        iteration=i,
                        output=output,
                        duration_ms=iter_ms,
                        claimed_complete=claimed,
                    )
                )

                # -- check completion promise --
                if claimed:
                    self._state = LoopState.COMPLETED
                    completed_naturally = True
                    break

                # -- allow early exit --
                if self._config.allow_early_exit and not output.strip():
                    self._state = LoopState.COMPLETED
                    completed_naturally = True
                    break

                # -- cooldown (skip on last iteration) --
                if i < self._config.max_iterations and self._config.cooldown_s > 0:
                    time.sleep(self._config.cooldown_s)
            else:
                # exhausted all iterations without completion
                if self._state == LoopState.RUNNING:
                    self._state = LoopState.COMPLETED
        except Exception:
            if self._state == LoopState.RUNNING:
                self._state = LoopState.FAILED

        total_ms = int((time.monotonic() - start) * 1000)
        return LoopResult(
            config=self._config,
            iterations=tuple(self._iterations),
            state=self._state,
            total_duration_ms=total_ms,
            completed_naturally=completed_naturally,
        )

    # -- helpers ----------------------------------------------------------

    def _check_claimed_complete(self, output: str) -> bool:
        """Return True if the output satisfies the completion promise."""
        promise = self._config.completion_promise
        if promise is None:
            return False
        return promise.lower() in output.lower()


__all__ = [
    "AutonomousLoopRunner",
    "LoopResult",
]
