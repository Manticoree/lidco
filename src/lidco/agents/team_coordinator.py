"""TeamCoordinator — split a prompt into tasks and delegate to teammates."""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from lidco.agents.shared_task_list import SharedTaskList


@dataclass
class CoordinationResult:
    prompt: str
    tasks_created: int
    outputs: dict[str, str] = field(default_factory=dict)  # task_id -> result
    timed_out: bool = False
    errors: list[str] = field(default_factory=list)


class TeamCoordinator:
    """Coordinate work across teammate functions using SharedTaskList."""

    def __init__(self, team: object = None, mailbox: object = None) -> None:
        self.team = team
        self.mailbox = mailbox

    def run(
        self,
        prompt: str,
        teammate_fns: dict[str, Callable[[str], str]],
        timeout_s: float = 5.0,
    ) -> CoordinationResult:
        """
        1. Split prompt into N tasks (one per teammate_fn key).
        2. Add tasks to SharedTaskList.
        3. For each teammate, call teammate_fn(task.title) -> result.
        4. Collect results with timeout.
        5. Return CoordinationResult.
        """
        task_list = SharedTaskList()

        if not teammate_fns:
            task = task_list.add(prompt)
            task_list.complete(task.id, "(no teammates)")
            return CoordinationResult(
                prompt=prompt,
                tasks_created=1,
                outputs={task.id: "(no teammates)"},
            )

        n = len(teammate_fns)
        subtasks = self.split_prompt(prompt, n)
        names = list(teammate_fns.keys())

        # Create tasks
        created_tasks: list[tuple[str, str, str]] = []  # (task_id, name, title)
        for i, name in enumerate(names):
            title = subtasks[i] if i < len(subtasks) else prompt
            task = task_list.add(title)
            created_tasks.append((task.id, name, title))

        result = CoordinationResult(prompt=prompt, tasks_created=len(created_tasks))

        # Run teammates concurrently
        threads: list[threading.Thread] = []
        lock = threading.Lock()

        def _worker(task_id: str, name: str, title: str) -> None:
            try:
                fn = teammate_fns[name]
                output = fn(title)
                task_list.complete(task_id, output)
                with lock:
                    result.outputs[task_id] = output
            except Exception as exc:
                task_list.fail(task_id, str(exc))
                with lock:
                    result.errors.append(f"{name}: {exc}")

        for task_id, name, title in created_tasks:
            t = threading.Thread(target=_worker, args=(task_id, name, title))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=timeout_s)

        # Check if any threads are still alive (timed out)
        for t in threads:
            if t.is_alive():
                result.timed_out = True
                break

        return result

    def split_prompt(self, prompt: str, n: int) -> list[str]:
        """
        Heuristic split:
        - If prompt has numbered lines (1. 2. 3.) use those.
        - If n==1 return [prompt].
        - Else split by sentences, distribute evenly.
        """
        if n <= 1:
            return [prompt]

        # Try numbered lines
        numbered = re.findall(r"^\s*\d+[\.\)]\s*(.+)", prompt, re.MULTILINE)
        if len(numbered) >= n:
            return numbered[:n]

        # Split by sentences
        sentences = re.split(r"(?<=[.!?])\s+", prompt.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= n:
            # Pad with the original prompt if not enough sentences
            while len(sentences) < n:
                sentences.append(prompt)
            return sentences[:n]

        # Distribute evenly
        chunk_size = len(sentences) // n
        result: list[str] = []
        for i in range(n):
            start = i * chunk_size
            if i == n - 1:
                chunk = sentences[start:]
            else:
                chunk = sentences[start : start + chunk_size]
            result.append(" ".join(chunk))
        return result
