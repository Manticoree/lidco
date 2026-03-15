"""Specification generator — Task 287.

Generates structured YAML+Markdown specifications for features/tasks
and saves them to ``.lidco/specs/``.

Usage::

    writer = SpecWriter(session)
    spec = await writer.generate("add rate limiting to API")
    path = writer.save(spec)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.core.session import Session

logger = logging.getLogger(__name__)

_SPECS_DIR = Path(".lidco") / "specs"

_SPEC_SYSTEM = """\
You are a senior software architect writing a technical specification.
Output a structured Markdown document with exactly these sections:

## Goal
One clear sentence.

## Background
Why this is needed (2-3 sentences).

## Inputs
Bullet list of inputs/parameters.

## Outputs
Bullet list of expected outputs/return values.

## Acceptance Criteria
Numbered list of specific, testable criteria.

## Edge Cases
Numbered list of edge cases and error conditions.

## Implementation Notes
Key design decisions, patterns, or constraints.

## Test File Location
Single file path, e.g. tests/unit/test_feature.py

## Implementation File Location
Single file path, e.g. src/package/feature.py
"""


@dataclass
class Spec:
    """A structured feature specification."""

    task: str
    content: str  # full Markdown text
    path: str = ""  # saved file path

    @property
    def goal(self) -> str:
        m = re.search(r"## Goal\s*\n([^\n#]+)", self.content)
        return m.group(1).strip() if m else self.task

    @property
    def test_file(self) -> str | None:
        m = re.search(r"## Test File Location\s*\n([^\n#]+)", self.content, re.IGNORECASE)
        if m:
            return m.group(1).strip().strip("`")
        return None

    @property
    def impl_file(self) -> str | None:
        m = re.search(r"## Implementation File Location\s*\n([^\n#]+)", self.content, re.IGNORECASE)
        if m:
            return m.group(1).strip().strip("`")
        return None

    @property
    def acceptance_criteria(self) -> list[str]:
        m = re.search(r"## Acceptance Criteria\s*\n(.*?)(?=\n##|\Z)", self.content, re.DOTALL)
        if not m:
            return []
        text = m.group(1)
        return [line.lstrip("0123456789. ").strip() for line in text.splitlines() if line.strip()]


class SpecWriter:
    """Generates and saves feature specifications.

    Args:
        session: Active LIDCO session for LLM access.
        specs_dir: Directory to save specs (default: .lidco/specs/).
    """

    def __init__(
        self,
        session: "Session",
        specs_dir: Path | None = None,
    ) -> None:
        self._session = session
        self._specs_dir = specs_dir or Path.cwd() / ".lidco" / "specs"

    async def generate(self, task: str, context: str = "") -> Spec:
        """Generate a specification for *task* using the LLM.

        Args:
            task: Natural-language description of what to build.
            context: Optional additional context (e.g., existing code snippets).
        """
        user_prompt = f"Write a specification for: {task}"
        if context:
            user_prompt += f"\n\nContext:\n{context[:2000]}"

        try:
            response = await self._session.orchestrator.handle(
                user_prompt,
                agent_name="architect",
                context=_SPEC_SYSTEM,
            )
            content = response.content if hasattr(response, "content") else str(response)
        except Exception as exc:
            logger.warning("SpecWriter: LLM call failed: %s", exc)
            content = f"## Goal\n{task}\n\n## Acceptance Criteria\n1. Feature works as described."

        return Spec(task=task, content=content)

    def save(self, spec: Spec, filename: str | None = None) -> str:
        """Save a spec to disk and return the file path."""
        self._specs_dir.mkdir(parents=True, exist_ok=True)
        if not filename:
            slug = re.sub(r"[^a-z0-9]+", "_", spec.task.lower())[:40]
            filename = f"{slug}.md"
        p = self._specs_dir / filename
        p.write_text(spec.content, encoding="utf-8")
        spec.path = str(p)
        logger.info("SpecWriter: saved spec to %s", p)
        return str(p)

    def list_specs(self) -> list[dict]:
        """Return a list of saved specs (path, goal)."""
        if not self._specs_dir.exists():
            return []
        specs: list[dict] = []
        for p in sorted(self._specs_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            content = p.read_text(encoding="utf-8", errors="replace")
            spec = Spec(task=p.stem, content=content, path=str(p))
            specs.append({"path": str(p), "goal": spec.goal, "name": p.stem})
        return specs

    def load(self, name_or_path: str) -> Spec | None:
        """Load a saved spec by filename stem or full path."""
        p = Path(name_or_path)
        if not p.exists():
            p = self._specs_dir / f"{name_or_path}.md"
        if not p.exists():
            return None
        content = p.read_text(encoding="utf-8", errors="replace")
        return Spec(task=p.stem, content=content, path=str(p))
