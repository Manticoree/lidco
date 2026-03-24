"""WorkflowAgent — scheduled recurring task agent."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable


class WorkflowStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"


@dataclass
class WorkflowRun:
    workflow_name: str
    started_at: float
    finished_at: float | None = None
    status: WorkflowStatus = WorkflowStatus.RUNNING
    output: str = ""


@dataclass
class WorkflowAgent:
    name: str
    schedule: str  # cron expression or "manual"
    tasks: list[str]
    notify: list[str] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.IDLE
    last_run: WorkflowRun | None = None

    def run(self, executor: Callable[[str], str] | None = None) -> WorkflowRun:
        """Execute all tasks. Returns a WorkflowRun."""
        run = WorkflowRun(workflow_name=self.name, started_at=time.time())
        self.status = WorkflowStatus.RUNNING
        outputs = []
        for task in self.tasks:
            try:
                if executor:
                    out = executor(task)
                else:
                    out = f"executed: {task}"
                outputs.append(out)
            except Exception as exc:
                run.status = WorkflowStatus.FAILED
                run.output = str(exc)
                run.finished_at = time.time()
                self.status = WorkflowStatus.FAILED
                self.last_run = run
                return run

        run.status = WorkflowStatus.DONE
        run.output = "\n".join(outputs)
        run.finished_at = time.time()
        self.status = WorkflowStatus.IDLE
        self.last_run = run
        return run


class WorkflowRegistry:
    """Registry of WorkflowAgent instances."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._workflows: dict[str, WorkflowAgent] = {}
        self._project_dir = project_dir or Path.cwd()

    def add(self, agent: WorkflowAgent) -> None:
        self._workflows[agent.name] = agent

    def get(self, name: str) -> WorkflowAgent | None:
        return self._workflows.get(name)

    def list(self) -> list[WorkflowAgent]:
        return list(self._workflows.values())

    def remove(self, name: str) -> bool:
        if name in self._workflows:
            del self._workflows[name]
            return True
        return False
