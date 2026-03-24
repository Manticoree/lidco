"""SpecWriter — converts a natural-language description into requirements.md.

Uses EARS (Easy Approach to Requirements Syntax) notation:
  "The system shall <action> when <condition>."
"""
from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SPEC_DIR = ".lidco/spec"
_REQ_FILE = "requirements.md"

_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a senior requirements engineer.  Given a feature description, produce a
    structured requirements document using EARS notation for acceptance criteria.

    Respond in JSON with exactly this schema:
    {
      "title": "<short feature title>",
      "overview": "<2-3 sentence summary>",
      "user_stories": ["As a ... I want ... so that ...", ...],
      "acceptance_criteria": ["The system shall ... when ...", ...],
      "out_of_scope": ["...", ...]
    }

    Rules:
    - acceptance_criteria items MUST start with "The system shall"
    - user_stories items MUST follow "As a <role> I want <goal> so that <reason>"
    - out_of_scope items are explicit exclusions to prevent scope creep
    - Produce 3-6 user stories, 5-10 acceptance criteria, 2-4 out_of_scope items
""")


@dataclass
class SpecDocument:
    title: str
    overview: str
    user_stories: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title}",
            "",
            "## Overview",
            "",
            self.overview,
            "",
            "## User Stories",
            "",
        ]
        for story in self.user_stories:
            lines.append(f"- {story}")
        lines += [
            "",
            "## Acceptance Criteria",
            "",
        ]
        for i, crit in enumerate(self.acceptance_criteria, 1):
            lines.append(f"{i}. {crit}")
        lines += [
            "",
            "## Out of Scope",
            "",
        ]
        for item in self.out_of_scope:
            lines.append(f"- {item}")
        lines.append("")
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str) -> "SpecDocument":
        """Parse a previously saved requirements.md back into a SpecDocument."""
        title = ""
        overview_lines: list[str] = []
        user_stories: list[str] = []
        acceptance_criteria: list[str] = []
        out_of_scope: list[str] = []

        section = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# ") and not title:
                title = stripped[2:]
            elif stripped == "## Overview":
                section = "overview"
            elif stripped == "## User Stories":
                section = "stories"
            elif stripped == "## Acceptance Criteria":
                section = "criteria"
            elif stripped == "## Out of Scope":
                section = "scope"
            elif stripped.startswith("## "):
                section = None
            elif section == "overview" and stripped:
                overview_lines.append(stripped)
            elif section == "stories" and stripped.startswith("- "):
                user_stories.append(stripped[2:])
            elif section == "criteria" and stripped and stripped[0].isdigit():
                # "1. The system shall..."
                parts = stripped.split(". ", 1)
                if len(parts) == 2:
                    acceptance_criteria.append(parts[1])
            elif section == "scope" and stripped.startswith("- "):
                out_of_scope.append(stripped[2:])

        return cls(
            title=title,
            overview=" ".join(overview_lines),
            user_stories=user_stories,
            acceptance_criteria=acceptance_criteria,
            out_of_scope=out_of_scope,
        )


class SpecWriter:
    """Generates a requirements.md from a natural-language description."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm = llm_client  # callable(messages) -> str, or None for offline mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, description: str, project_dir: Path) -> SpecDocument:
        """Generate (or update) requirements.md from *description*.

        If requirements.md already exists, it is loaded as context so
        incremental updates preserve existing decisions.
        """
        existing_context = self._load_existing(project_dir)
        doc = self._call_llm(description, existing_context)
        self._save(doc, project_dir)
        return doc

    def load(self, project_dir: Path) -> SpecDocument | None:
        """Load existing requirements.md, returns None if absent."""
        p = self._req_path(project_dir)
        if not p.exists():
            return None
        return SpecDocument.from_markdown(p.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _req_path(self, project_dir: Path) -> Path:
        return project_dir / _SPEC_DIR / _REQ_FILE

    def _load_existing(self, project_dir: Path) -> str:
        p = self._req_path(project_dir)
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    def _call_llm(self, description: str, existing_context: str) -> SpecDocument:
        if self._llm is None:
            return self._offline_generate(description)

        user_content = f"Feature description:\n{description}"
        if existing_context:
            user_content += f"\n\nExisting requirements (for context):\n{existing_context}"

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        raw = self._llm(messages)
        return self._parse_json(raw)

    def _offline_generate(self, description: str) -> SpecDocument:
        """Minimal deterministic generation used when no LLM is wired up."""
        title = description.split(".")[0][:60].strip() or "Feature"
        return SpecDocument(
            title=title,
            overview=description,
            user_stories=[f"As a user I want {title.lower()} so that I can be productive"],
            acceptance_criteria=[f"The system shall implement {title.lower()} when requested"],
            out_of_scope=["Non-related features"],
        )

    def _parse_json(self, raw: str) -> SpecDocument:
        import json
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        data = json.loads(text)
        return SpecDocument(
            title=data.get("title", ""),
            overview=data.get("overview", ""),
            user_stories=data.get("user_stories", []),
            acceptance_criteria=data.get("acceptance_criteria", []),
            out_of_scope=data.get("out_of_scope", []),
        )

    def _save(self, doc: SpecDocument, project_dir: Path) -> None:
        p = self._req_path(project_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc.to_markdown(), encoding="utf-8")
        logger.info("Saved requirements to %s", p)
