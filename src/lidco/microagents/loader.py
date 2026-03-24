"""Keyword-triggered knowledge files injected into system prompt."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Microagent:
    name: str
    content: str
    triggers: list[str]
    priority: int = 0
    source_path: str = ""


class MicroagentLoader:
    """Loads .md microagent files from .lidco/microagents/ directories."""

    FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    TRIGGERS_RE = re.compile(r"triggers:\s*\[([^\]]*)\]")
    PRIORITY_RE = re.compile(r"priority:\s*(\d+)")

    def load_file(self, path: Path) -> Microagent | None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        m = self.FRONTMATTER_RE.match(text)
        if not m:
            return None
        front = m.group(1)
        body = text[m.end():]
        triggers_m = self.TRIGGERS_RE.search(front)
        if not triggers_m:
            return None
        triggers = [t.strip().strip("\"'") for t in triggers_m.group(1).split(",") if t.strip()]
        priority_m = self.PRIORITY_RE.search(front)
        priority = int(priority_m.group(1)) if priority_m else 0
        return Microagent(
            name=path.stem,
            content=body.strip(),
            triggers=triggers,
            priority=priority,
            source_path=str(path),
        )

    def load_all(self, project_dir: Path | str) -> list[Microagent]:
        """Load from .lidco/microagents/ (project) and ~/.lidco/microagents/ (global)."""
        result: list[Microagent] = []
        dirs_to_check = [
            Path(project_dir) / ".lidco" / "microagents",
            Path.home() / ".lidco" / "microagents",
        ]
        for d in dirs_to_check:
            if d.is_dir():
                for f in d.glob("*.md"):
                    ma = self.load_file(f)
                    if ma:
                        result.append(ma)
        return result


class MicroagentMatcher:
    """Matches user messages against microagent trigger keywords."""

    def match(self, user_message: str, microagents: list[Microagent]) -> list[Microagent]:
        msg_lower = user_message.lower()
        matched = []
        for ma in microagents:
            if any(t.lower() in msg_lower for t in ma.triggers):
                matched.append(ma)
        return sorted(matched, key=lambda x: x.priority, reverse=True)

    def format_for_prompt(self, matched: list[Microagent]) -> str:
        if not matched:
            return ""
        lines = ["## Project Knowledge\n"]
        for ma in matched:
            lines.append(f"### {ma.name}\n{ma.content}\n")
        return "\n".join(lines)
