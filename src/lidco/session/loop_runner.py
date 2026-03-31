"""Loop Runner — recurring command execution (Q165/Task 940)."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class LoopConfig:
    """Configuration for a recurring command loop."""

    command: str
    interval_seconds: int
    max_iterations: int = 0  # 0 = infinite
    stop_on_error: bool = False


class LoopRunner:
    """Execute a command on a recurring interval."""

    def __init__(self, config: LoopConfig) -> None:
        self._config = config
        self._running: bool = False
        self._results: list[dict] = []
        self._iteration: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, execute_fn: Callable[[str], str]) -> None:
        """Run the loop synchronously (blocking), storing results.

        Each iteration calls *execute_fn(command)* and records the
        timestamped result.  The loop terminates when :meth:`stop` is
        called, *max_iterations* is reached, or an error occurs with
        *stop_on_error* enabled.
        """
        self._running = True
        self._iteration = 0

        while self._running:
            if 0 < self._config.max_iterations <= self._iteration:
                self._running = False
                break

            try:
                output = execute_fn(self._config.command)
                self._results.append({
                    "iteration": self._iteration,
                    "timestamp": time.time(),
                    "command": self._config.command,
                    "output": output,
                    "error": None,
                })
            except Exception as exc:
                self._results.append({
                    "iteration": self._iteration,
                    "timestamp": time.time(),
                    "command": self._config.command,
                    "output": None,
                    "error": str(exc),
                })
                if self._config.stop_on_error:
                    self._running = False
                    break

            self._iteration += 1

            # Sleep unless stopped (check after increment so stop() can break)
            if self._running and (
                self._config.max_iterations == 0
                or self._iteration < self._config.max_iterations
            ):
                time.sleep(self._config.interval_seconds)

    def stop(self) -> None:
        """Signal the loop to stop after the current iteration."""
        self._running = False

    @property
    def is_running(self) -> bool:
        """Whether the loop is currently executing."""
        return self._running

    def results(self) -> list[dict]:
        """Return all recorded results (timestamped)."""
        return list(self._results)

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_interval(spec: str) -> int:
        """Parse a human-friendly interval like ``'5m'``, ``'30s'``, ``'1h'`` to seconds.

        Plain integers are treated as seconds.  Raises ``ValueError`` on bad input.
        """
        spec = spec.strip().lower()
        if not spec:
            raise ValueError("Empty interval specification.")

        m = re.fullmatch(r"(\d+)\s*(s|m|h)?", spec)
        if not m:
            raise ValueError(f"Invalid interval: '{spec}'")

        value = int(m.group(1))
        unit = m.group(2) or "s"
        multipliers = {"s": 1, "m": 60, "h": 3600}
        return value * multipliers[unit]
