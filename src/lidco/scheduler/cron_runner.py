"""CronRunner — lightweight cron-style task scheduler."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable


@dataclass
class ScheduledTask:
    name: str
    cron_expr: str
    instruction: str
    enabled: bool = True
    last_run: float | None = None
    run_count: int = 0


@dataclass
class RunResult:
    task_name: str
    started_at: float
    finished_at: float
    success: bool
    output: str
    error: str | None = None


class CronRunner:
    """Run tasks on a cron schedule, persisting state to JSON."""

    _DEFAULT_STATE = Path(".lidco/scheduler.json")

    def __init__(self, state_path: Path | None = None) -> None:
        self._state_path = state_path or self._DEFAULT_STATE
        self._tasks: dict[str, ScheduledTask] = {}

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def add_task(self, name: str, cron_expr: str, instruction: str) -> ScheduledTask:
        """Validate cron_expr (5 fields), store and return ScheduledTask."""
        fields = cron_expr.strip().split()
        if len(fields) != 5:
            raise ValueError(f"Invalid cron expression (need 5 fields): {cron_expr!r}")
        task = ScheduledTask(name=name, cron_expr=cron_expr, instruction=instruction)
        self._tasks = {**self._tasks, name: task}
        return task

    def remove_task(self, name: str) -> bool:
        """Remove task by name. Returns True if removed, False if not found."""
        if name not in self._tasks:
            return False
        self._tasks = {k: v for k, v in self._tasks.items() if k != name}
        return True

    def list_tasks(self) -> list[ScheduledTask]:
        """Return list of all tasks."""
        return list(self._tasks.values())

    # ------------------------------------------------------------------
    # Scheduling logic
    # ------------------------------------------------------------------

    def is_due(self, task: ScheduledTask, now: float | None = None) -> bool:
        """Return True if task should run at the given time (or current time)."""
        now_ts = now if now is not None else time.time()

        # Avoid double-fire: must be at least 60s since last_run
        if task.last_run is not None and (now_ts - task.last_run) < 60:
            return False

        parsed = self.parse_cron(task.cron_expr)
        import datetime
        dt = datetime.datetime.fromtimestamp(now_ts)

        checks = {
            "minute": dt.minute,
            "hour": dt.hour,
            "day": dt.day,
            "month": dt.month,
            "weekday": dt.weekday(),  # 0=Monday in Python; cron uses 0=Sunday but we keep simple
        }

        for field_name, current_val in checks.items():
            expected = parsed.get(field_name)
            if expected is not None and expected != current_val:
                return False

        return True

    def tick(
        self,
        executor: Callable[[str], str] | None = None,
        now: float | None = None,
    ) -> list[RunResult]:
        """Run all enabled due tasks; return results."""
        _executor = executor if executor is not None else (lambda i: f"[stub] ran: {i}")
        now_ts = now if now is not None else time.time()
        results: list[RunResult] = []

        for task in list(self._tasks.values()):
            if not task.enabled:
                continue
            if not self.is_due(task, now=now_ts):
                continue

            started = now_ts
            output = ""
            error: str | None = None
            success = True
            try:
                output = _executor(task.instruction)
            except Exception as exc:
                error = str(exc)
                success = False

            finished = time.time()

            # Update task state (immutable replacement)
            updated = ScheduledTask(
                name=task.name,
                cron_expr=task.cron_expr,
                instruction=task.instruction,
                enabled=task.enabled,
                last_run=now_ts,
                run_count=task.run_count + 1,
            )
            self._tasks = {**self._tasks, task.name: updated}

            results.append(RunResult(
                task_name=task.name,
                started_at=started,
                finished_at=finished,
                success=success,
                output=output,
                error=error,
            ))

        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_state(self) -> None:
        """Write tasks to JSON state file."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            name: asdict(task)
            for name, task in self._tasks.items()
        }
        self._state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_state(self) -> None:
        """Load tasks from JSON state file; ignore if file not found."""
        if not self._state_path.is_file():
            return
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            tasks: dict[str, ScheduledTask] = {}
            for name, item in data.items():
                tasks[name] = ScheduledTask(
                    name=item["name"],
                    cron_expr=item["cron_expr"],
                    instruction=item["instruction"],
                    enabled=item.get("enabled", True),
                    last_run=item.get("last_run"),
                    run_count=item.get("run_count", 0),
                )
            self._tasks = tasks
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Cron parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_cron(expr: str) -> dict:
        """Parse 5-field cron expression into dict of int|None per field.

        Returns:
            {"minute": int|None, "hour": int|None, "day": int|None,
             "month": int|None, "weekday": int|None}
        """
        field_names = ["minute", "hour", "day", "month", "weekday"]
        fields = expr.strip().split()
        if len(fields) != 5:
            raise ValueError(f"Expected 5 cron fields, got {len(fields)}: {expr!r}")

        result: dict = {}
        for name, value in zip(field_names, fields):
            if value == "*":
                result[name] = None
            else:
                result[name] = int(value)
        return result
