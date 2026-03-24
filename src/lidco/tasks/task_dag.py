"""Long-horizon task DAG with checkpoints — Replit Agent 3 / Devin parity."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable


TaskStatus = str  # "pending" | "running" | "done" | "failed" | "skipped"


@dataclass
class DAGTask:
    id: str
    name: str
    description: str
    depends_on: list[str] = field(default_factory=list)  # task IDs
    status: TaskStatus = "pending"
    result: Any = None
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def duration(self) -> float:
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at
        return 0.0


@dataclass
class DAGResult:
    completed: int
    failed: int
    skipped: int
    total: int

    @property
    def success(self) -> bool:
        return self.failed == 0

    def format_summary(self) -> str:
        return f"DAG: {self.completed}/{self.total} done, {self.failed} failed, {self.skipped} skipped"


class TaskDAG:
    """Directed acyclic graph of tasks with dependency resolution and checkpointing.

    Tasks run in topological order. Failed tasks cause dependents to be skipped.
    State is persisted to a JSON checkpoint file for resume-on-failure.
    """

    def __init__(self, name: str = "dag", checkpoint_path: str | None = None) -> None:
        self.name = name
        self._tasks: dict[str, DAGTask] = {}
        self._checkpoint = Path(checkpoint_path) if checkpoint_path else None

    def add_task(self, task: DAGTask) -> None:
        self._tasks[task.id] = task

    def add(self, id: str, name: str, description: str = "", depends_on: list[str] | None = None) -> DAGTask:
        t = DAGTask(id=id, name=name, description=description, depends_on=depends_on or [])
        self.add_task(t)
        return t

    def _topo_order(self) -> list[str]:
        """Kahn's algorithm for topological sort."""
        in_degree: dict[str, int] = {tid: 0 for tid in self._tasks}
        for task in self._tasks.values():
            for dep in task.depends_on:
                if dep in in_degree:
                    in_degree[task.id] = in_degree.get(task.id, 0) + 1

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        order: list[str] = []
        while queue:
            queue.sort()  # deterministic
            tid = queue.pop(0)
            order.append(tid)
            for other in self._tasks.values():
                if tid in other.depends_on:
                    in_degree[other.id] -= 1
                    if in_degree[other.id] == 0:
                        queue.append(other.id)
        return order

    def _deps_satisfied(self, task: DAGTask) -> bool:
        for dep_id in task.depends_on:
            dep = self._tasks.get(dep_id)
            if dep is None or dep.status != "done":
                return False
        return True

    def _deps_failed(self, task: DAGTask) -> bool:
        for dep_id in task.depends_on:
            dep = self._tasks.get(dep_id)
            if dep and dep.status in ("failed", "skipped"):
                return True
        return False

    def save_checkpoint(self) -> None:
        if self._checkpoint is None:
            return
        self._checkpoint.parent.mkdir(parents=True, exist_ok=True)
        data = {tid: vars(t) for tid, t in self._tasks.items()}
        self._checkpoint.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_checkpoint(self) -> bool:
        if self._checkpoint is None or not self._checkpoint.exists():
            return False
        try:
            data = json.loads(self._checkpoint.read_text(encoding="utf-8"))
            for tid, d in data.items():
                if tid in self._tasks:
                    t = self._tasks[tid]
                    t.status = d.get("status", "pending")
                    t.result = d.get("result")
                    t.error = d.get("error", "")
                    t.started_at = d.get("started_at", 0.0)
                    t.finished_at = d.get("finished_at", 0.0)
            return True
        except Exception:
            return False

    async def run(
        self,
        runner: Callable[[DAGTask], Awaitable[Any]],
        *,
        resume: bool = False,
    ) -> DAGResult:
        """Execute all tasks in topological order.

        Args:
            runner: async fn(task) -> result. Should raise on failure.
            resume: If True, skip already-done tasks (load checkpoint first).
        """
        if resume:
            self.load_checkpoint()

        order = self._topo_order()
        completed = failed = skipped = 0

        for tid in order:
            task = self._tasks[tid]
            if task.status == "done":
                completed += 1
                continue
            if self._deps_failed(task):
                task.status = "skipped"
                skipped += 1
                self.save_checkpoint()
                continue
            task.status = "running"
            task.started_at = time.monotonic()
            try:
                task.result = await runner(task)
                task.status = "done"
                task.finished_at = time.monotonic()
                completed += 1
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                task.finished_at = time.monotonic()
                failed += 1
            self.save_checkpoint()

        return DAGResult(completed=completed, failed=failed, skipped=skipped, total=len(self._tasks))

    def format_plan(self) -> str:
        order = self._topo_order()
        lines = [f"Task DAG: {self.name} ({len(self._tasks)} tasks)"]
        icons = {"pending": "○", "running": "→", "done": "✓", "failed": "✗", "skipped": "-"}
        for tid in order:
            task = self._tasks[tid]
            icon = icons.get(task.status, "?")
            dep_str = f" (needs: {', '.join(task.depends_on)})" if task.depends_on else ""
            lines.append(f"  {icon} [{task.id}] {task.name}{dep_str}")
        return "\n".join(lines)

    def get_task(self, tid: str) -> DAGTask | None:
        return self._tasks.get(tid)

    def pending_tasks(self) -> list[DAGTask]:
        return [t for t in self._tasks.values() if t.status == "pending"]
