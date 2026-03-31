"""TaskScheduler — persistent one-shot + recurring task scheduler (stdlib only)."""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

_DEFAULT_STORE = Path(".lidco") / "scheduled_tasks.json"
_INTERVAL_RE = re.compile(r"^every\s+(\d+)(s|m|h)$", re.IGNORECASE)
_MULTIPLIERS = {"s": 1, "m": 60, "h": 3600}


@dataclass
class ScheduledTask:
    id: str
    name: str
    command: str
    schedule: str  # ISO datetime or "every Ns/Nm/Nh"
    next_run: float  # epoch timestamp
    enabled: bool = True
    last_run: float | None = None
    last_result: str = ""
    run_count: int = 0
    timeout: float = 300.0


@dataclass
class TaskRunResult:
    task_id: str
    task_name: str
    command: str
    started_at: float
    finished_at: float
    returncode: int
    stdout: str
    stderr: str
    success: bool

    def format_summary(self) -> str:
        status = "OK" if self.success else f"ERROR (rc={self.returncode})"
        elapsed = self.finished_at - self.started_at
        lines = [
            f"Task: {self.task_name} [{self.task_id}]",
            f"Command: {self.command}",
            f"Status: {status}  Elapsed: {elapsed:.2f}s",
        ]
        if self.stdout.strip():
            lines.append(f"stdout:\n{self.stdout.strip()}")
        if self.stderr.strip():
            lines.append(f"stderr:\n{self.stderr.strip()}")
        return "\n".join(lines)


class TaskScheduler:
    """
    Persistent one-shot + recurring task scheduler.

    Parameters
    ----------
    store_path:
        Path to the JSON persistence file.  Defaults to
        ``.lidco/scheduled_tasks.json``.
    """

    def __init__(self, store_path: Path | None = None) -> None:
        self._store_path = Path(store_path) if store_path is not None else _DEFAULT_STORE
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- private

    def _parse_schedule(self, schedule: str) -> float:
        """Return the *next_run* epoch timestamp for *schedule*.

        Raises
        ------
        ValueError
            If *schedule* does not match a recognised format.
        """
        m = _INTERVAL_RE.match(schedule.strip())
        if m:
            n, unit = int(m.group(1)), m.group(2).lower()
            return time.time() + n * _MULTIPLIERS[unit]
        # Try ISO datetime
        try:
            return datetime.fromisoformat(schedule.strip()).timestamp()
        except (ValueError, TypeError):
            pass
        raise ValueError(
            f"Unrecognised schedule format {schedule!r}. "
            "Use 'every Ns/Nm/Nh' or an ISO datetime string."
        )

    def _is_recurring(self, schedule: str) -> bool:
        return bool(_INTERVAL_RE.match(schedule.strip()))

    def _compute_next_run(self, task: ScheduledTask) -> float:
        """Recompute next_run for a recurring task from *now*."""
        m = _INTERVAL_RE.match(task.schedule.strip())
        if m:
            n, unit = int(m.group(1)), m.group(2).lower()
            return time.time() + n * _MULTIPLIERS[unit]
        return task.next_run  # should never reach here for one-shot

    def _execute_task(self, task: ScheduledTask) -> TaskRunResult:
        started = time.time()
        try:
            proc = subprocess.run(
                task.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=task.timeout,
            )
            finished = time.time()
            return TaskRunResult(
                task_id=task.id,
                task_name=task.name,
                command=task.command,
                started_at=started,
                finished_at=finished,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                success=proc.returncode == 0,
            )
        except subprocess.TimeoutExpired:
            finished = time.time()
            return TaskRunResult(
                task_id=task.id,
                task_name=task.name,
                command=task.command,
                started_at=started,
                finished_at=finished,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {task.timeout}s",
                success=False,
            )
        except Exception as exc:  # noqa: BLE001
            finished = time.time()
            return TaskRunResult(
                task_id=task.id,
                task_name=task.name,
                command=task.command,
                started_at=started,
                finished_at=finished,
                returncode=-1,
                stdout="",
                stderr=str(exc),
                success=False,
            )

    def _load(self) -> dict[str, dict]:
        if not self._store_path.exists():
            return {}
        try:
            return json.loads(self._store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_data(self, data: dict[str, dict]) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(
            json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
        )

    # -------------------------------------------------------------- public API

    def add(self, name: str, command: str, schedule: str) -> ScheduledTask:
        """Add a new task.  Raises *ValueError* for invalid schedule."""
        next_run = self._parse_schedule(schedule)
        task = ScheduledTask(
            id=uuid.uuid4().hex,
            name=name,
            command=command,
            schedule=schedule,
            next_run=next_run,
        )
        with self._lock:
            data = self._load()
            data = {**data, task.id: asdict(task)}
            self._save_data(data)
        return task

    def remove(self, task_id: str) -> bool:
        """Remove task by *task_id*.  Returns *True* if it existed."""
        with self._lock:
            data = self._load()
            if task_id not in data:
                return False
            new_data = {k: v for k, v in data.items() if k != task_id}
            self._save_data(new_data)
            return True

    def list(self) -> list[ScheduledTask]:
        """Return all tasks sorted by next_run."""
        data = self._load()
        tasks = [ScheduledTask(**v) for v in data.values()]
        return sorted(tasks, key=lambda t: t.next_run)

    def get(self, task_id: str) -> ScheduledTask | None:
        """Return the task with *task_id* or *None*."""
        data = self._load()
        entry = data.get(task_id)
        return ScheduledTask(**entry) if entry else None

    def run_due(self) -> list[TaskRunResult]:
        """Execute all enabled tasks whose *next_run* is in the past."""
        now = time.time()
        results: list[TaskRunResult] = []
        with self._lock:
            data = self._load()
            updated = dict(data)
            for task_id, entry in data.items():
                task = ScheduledTask(**entry)
                if not task.enabled or task.next_run > now:
                    continue
                result = self._execute_task(task)
                results.append(result)
                # Update task record immutably
                updated_task = ScheduledTask(
                    id=task.id,
                    name=task.name,
                    command=task.command,
                    schedule=task.schedule,
                    next_run=self._compute_next_run(task) if self._is_recurring(task.schedule) else task.next_run,
                    enabled=False if not self._is_recurring(task.schedule) else True,
                    last_run=result.started_at,
                    last_result="ok" if result.success else f"error: rc={result.returncode}",
                    run_count=task.run_count + 1,
                )
                updated = {**updated, task_id: asdict(updated_task)}
            self._save_data(updated)
        return results

    def start(self, poll_interval: float = 5.0) -> None:
        """Start a background daemon thread that calls *run_due* periodically."""
        self._stop_event.clear()

        def _loop() -> None:
            while not self._stop_event.wait(poll_interval):
                self.run_due()

        self._thread = threading.Thread(target=_loop, daemon=True, name="task-scheduler")
        self._thread.start()

    def stop(self) -> None:
        """Stop the background thread (waits up to 2 s for clean shutdown)."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
