"""Load workflow definitions from .lidco/workflows/*.md -- Q162."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkflowDef:
    """A workflow loaded from a markdown file."""

    name: str
    title: str
    description: str
    steps: list[str]
    source_path: str


class WorkflowLoader:
    """Discover and parse ``*.md`` workflow files.

    Each markdown file may contain optional YAML-style front-matter between
    ``---`` markers (for *title* and *description*) followed by markdown
    content where list items (``- ...`` or ``1. ...``) are extracted as
    workflow steps.
    """

    def __init__(self, workflows_dir: str = ".lidco/workflows") -> None:
        self._workflows_dir = workflows_dir

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_all(self) -> list[WorkflowDef]:
        """Scan the workflows directory and parse every ``*.md`` file."""
        wdir = Path(self._workflows_dir)
        if not wdir.is_dir():
            return []

        results: list[WorkflowDef] = []
        for md_path in sorted(wdir.glob("*.md")):
            wf = self._parse_file(md_path)
            if wf is not None:
                results.append(wf)
        return results

    def load_one(self, name: str) -> WorkflowDef | None:
        """Load a single workflow by *name* (stem of the md file)."""
        wdir = Path(self._workflows_dir)
        candidate = wdir / f"{name}.md"
        if not candidate.is_file():
            return None
        return self._parse_file(candidate)

    # ------------------------------------------------------------------
    # Command registration helper
    # ------------------------------------------------------------------

    def register_as_commands(self, registry: Any) -> None:
        """Register each workflow as a ``/workflow-<name>`` slash command."""
        from lidco.cli.commands.registry import SlashCommand

        for wf in self.load_all():
            cmd_name = f"workflow-{wf.name}"

            # Closure capture
            def _make_handler(workflow: WorkflowDef):
                async def _handler(args: str = "") -> str:
                    lines = [f"## {workflow.title}", ""]
                    if workflow.description:
                        lines.append(workflow.description)
                        lines.append("")
                    for i, step in enumerate(workflow.steps, 1):
                        lines.append(f"{i}. {step}")
                    return "\n".join(lines)
                return _handler

            registry.register(
                SlashCommand(
                    cmd_name,
                    wf.title or f"Workflow: {wf.name}",
                    _make_handler(wf),
                )
            )

    # ------------------------------------------------------------------
    # Parsing internals
    # ------------------------------------------------------------------

    def _parse_file(self, path: Path) -> WorkflowDef | None:
        """Parse a single markdown workflow file."""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None

        title = ""
        description = ""
        body = text

        # Parse optional YAML front-matter (between --- markers).
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if fm_match:
            fm_block = fm_match.group(1)
            body = text[fm_match.end():]
            for line in fm_block.splitlines():
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"').strip("'")

        # Extract steps from markdown list items.
        steps: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            # Unordered list: - step text
            if stripped.startswith("- "):
                steps.append(stripped[2:].strip())
            # Ordered list: 1. step text
            elif re.match(r"^\d+\.\s+", stripped):
                step_text = re.sub(r"^\d+\.\s+", "", stripped).strip()
                if step_text:
                    steps.append(step_text)

        name = path.stem

        if not title:
            title = name.replace("-", " ").replace("_", " ").title()

        return WorkflowDef(
            name=name,
            title=title,
            description=description,
            steps=steps,
            source_path=str(path),
        )
