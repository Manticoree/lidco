"""SpecContextProvider — injects spec documents into the agent system prompt.

When `.lidco/spec/requirements.md` exists, prepends a "## Project Specification"
block containing requirements and open tasks (max 2000 tokens / ~8000 chars).
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SPEC_DIR = ".lidco/spec"
_MAX_CHARS = 8000  # ~2000 tokens safety budget


class SpecContextProvider:
    """Loads spec documents and formats them for agent context injection."""

    def __init__(self, project_dir: Path | str | None = None) -> None:
        self._project_dir = Path(project_dir) if project_dir else Path.cwd()

    @property
    def project_dir(self) -> Path:
        return self._project_dir

    def load(self, project_dir: Path | str | None = None) -> str | None:
        """Return formatted spec context block, or None if no spec exists.

        The returned string is ready to be prepended to the system prompt.
        """
        base = Path(project_dir) if project_dir else self._project_dir
        req_path = base / _SPEC_DIR / "requirements.md"
        tasks_path = base / _SPEC_DIR / "tasks.md"

        if not req_path.exists():
            return None

        req_text = req_path.read_text(encoding="utf-8", errors="replace")
        tasks_text = ""
        if tasks_path.exists():
            tasks_text = self._filter_open_tasks(
                tasks_path.read_text(encoding="utf-8", errors="replace")
            )

        block = self._format_block(req_text, tasks_text)
        if len(block) > _MAX_CHARS:
            block = block[:_MAX_CHARS] + "\n...[spec truncated]\n"
        return block

    def spec_exists(self, project_dir: Path | str | None = None) -> bool:
        base = Path(project_dir) if project_dir else self._project_dir
        return (base / _SPEC_DIR / "requirements.md").exists()

    # ------------------------------------------------------------------

    def _filter_open_tasks(self, tasks_text: str) -> str:
        """Keep only unchecked tasks to reduce token usage."""
        lines = tasks_text.splitlines()
        open_lines: list[str] = []
        capture = False
        for line in lines:
            if line.startswith("# "):
                open_lines.append(line)
                continue
            if line.startswith("- [ ]"):
                capture = True
                open_lines.append(line)
            elif line.startswith("- [x]"):
                capture = False
            elif capture and line.startswith("  "):
                open_lines.append(line)
            else:
                capture = False
        return "\n".join(open_lines)

    def _format_block(self, req_text: str, tasks_text: str) -> str:
        parts = [
            "## Project Specification",
            "",
            req_text.strip(),
        ]
        if tasks_text.strip():
            parts += [
                "",
                "### Open Tasks",
                "",
                tasks_text.strip(),
            ]
        parts.append("")
        return "\n".join(parts)
