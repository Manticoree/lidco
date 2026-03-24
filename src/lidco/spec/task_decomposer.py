"""TaskDecomposer — converts DesignDocument → tasks.md.

Produces an ordered, dependency-aware list of implementation tasks saved in
checkbox format.  Each task carries file targets and a short acceptance note.
"""
from __future__ import annotations

import logging
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lidco.spec.design_doc import DesignDocument

logger = logging.getLogger(__name__)

_SPEC_DIR = ".lidco/spec"
_TASKS_FILE = "tasks.md"

_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a tech lead decomposing a design document into implementation tasks.

    Respond in JSON with exactly this schema:
    {
      "tasks": [
        {
          "id": "T1",
          "title": "short title",
          "description": "what to implement",
          "target_files": ["src/..."],
          "depends_on": ["T0"],
          "done": false
        }
      ]
    }

    Rules:
    - IDs are T1, T2, T3, ... (T0 means no dependency)
    - depends_on lists IDs that MUST be done first
    - Order tasks so that dependencies come earlier in the list
    - 4-10 tasks total; each should be completable in <4 hours
""")


@dataclass
class SpecTask:
    id: str
    title: str
    description: str
    target_files: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    done: bool = False

    def to_checkbox_line(self) -> str:
        checkbox = "[x]" if self.done else "[ ]"
        deps = f" (depends: {', '.join(self.depends_on)})" if self.depends_on else ""
        return f"- {checkbox} {self.id}: {self.title}{deps}"

    def to_markdown_block(self) -> str:
        lines = [
            self.to_checkbox_line(),
            f"  {self.description}",
        ]
        if self.target_files:
            files = ", ".join(f"`{f}`" for f in self.target_files)
            lines.append(f"  Files: {files}")
        return "\n".join(lines)


class TaskDecomposer:
    """Decomposes a DesignDocument into an ordered list of SpecTasks."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm = llm_client

    def decompose(self, design: DesignDocument, project_dir: Path) -> list[SpecTask]:
        """Generate tasks from *design*, save tasks.md, return task list."""
        tasks = self._call_llm(design)
        tasks = self._topological_sort(tasks)
        self._save(tasks, project_dir)
        return tasks

    def load(self, project_dir: Path) -> list[SpecTask]:
        """Load existing tasks.md.  Returns empty list if absent."""
        p = self._tasks_path(project_dir)
        if not p.exists():
            return []
        return self._parse_markdown(p.read_text(encoding="utf-8"))

    def mark_done(self, task_id: str, project_dir: Path) -> bool:
        """Toggle task *task_id* to done=True.  Returns True if found."""
        tasks = self.load(project_dir)
        found = False
        for t in tasks:
            if t.id == task_id:
                t.done = True
                found = True
                break
        if found:
            self._save(tasks, project_dir)
        return found

    # ------------------------------------------------------------------

    def _tasks_path(self, project_dir: Path) -> Path:
        return project_dir / _SPEC_DIR / _TASKS_FILE

    def _call_llm(self, design: DesignDocument) -> list[SpecTask]:
        if self._llm is None:
            return self._offline_decompose(design)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Design document:\n\n{design.to_markdown()}"},
        ]
        raw = self._llm(messages)
        return self._parse_json(raw)

    def _offline_decompose(self, design: DesignDocument) -> list[SpecTask]:
        tasks: list[SpecTask] = []
        for i, comp in enumerate(design.components, 1):
            tasks.append(SpecTask(
                id=f"T{i}",
                title=f"Implement {comp.name}",
                description=comp.responsibility,
                target_files=[comp.file_path] if comp.file_path else [],
                depends_on=[f"T{i-1}"] if i > 1 else [],
            ))
        if not tasks:
            tasks.append(SpecTask(
                id="T1",
                title="Implement feature",
                description=design.implementation_notes or "Implement the designed feature.",
                target_files=[],
                depends_on=[],
            ))
        return tasks

    def _topological_sort(self, tasks: list[SpecTask]) -> list[SpecTask]:
        """Return tasks in dependency order (Kahn's algorithm)."""
        id_map = {t.id: t for t in tasks}
        in_degree: dict[str, int] = {t.id: 0 for t in tasks}
        for t in tasks:
            for dep in t.depends_on:
                if dep in in_degree:
                    in_degree[t.id] += 1

        queue = [t for t in tasks if in_degree[t.id] == 0]
        result: list[SpecTask] = []
        while queue:
            current = queue.pop(0)
            result.append(current)
            for t in tasks:
                if current.id in t.depends_on:
                    in_degree[t.id] -= 1
                    if in_degree[t.id] == 0:
                        queue.append(t)

        # Append any remaining (cycle case)
        seen = {t.id for t in result}
        for t in tasks:
            if t.id not in seen:
                result.append(t)
        return result

    def _parse_json(self, raw: str) -> list[SpecTask]:
        import json
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        data = json.loads(text)
        return [
            SpecTask(
                id=t.get("id", "T?"),
                title=t.get("title", ""),
                description=t.get("description", ""),
                target_files=t.get("target_files", []),
                depends_on=[d for d in t.get("depends_on", []) if d != "T0"],
                done=t.get("done", False),
            )
            for t in data.get("tasks", [])
        ]

    def _parse_markdown(self, text: str) -> list[SpecTask]:
        """Parse tasks.md back into SpecTask list."""
        tasks: list[SpecTask] = []
        current: dict[str, Any] | None = None
        for line in text.splitlines():
            m = re.match(r"^- \[([ x])\] (T\w+): (.+?)(?:\s+\(depends: (.+?)\))?$", line)
            if m:
                if current:
                    tasks.append(SpecTask(**current))
                done = m.group(1) == "x"
                deps_raw = m.group(4) or ""
                depends_on = [d.strip() for d in deps_raw.split(",") if d.strip()]
                current = {
                    "id": m.group(2),
                    "title": m.group(3).strip(),
                    "description": "",
                    "target_files": [],
                    "depends_on": depends_on,
                    "done": done,
                }
            elif current is not None:
                stripped = line.strip()
                if stripped.startswith("Files:"):
                    raw_files = stripped[6:].strip()
                    current["target_files"] = [
                        f.strip().strip("`") for f in raw_files.split(",") if f.strip()
                    ]
                elif stripped and not current["description"]:
                    current["description"] = stripped
        if current:
            tasks.append(SpecTask(**current))
        return tasks

    def _save(self, tasks: list[SpecTask], project_dir: Path) -> None:
        p = self._tasks_path(project_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Tasks\n"]
        for t in tasks:
            lines.append(t.to_markdown_block())
            lines.append("")
        p.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Saved tasks to %s", p)
