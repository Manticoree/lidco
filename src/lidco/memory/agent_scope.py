"""AgentMemoryScope — per-agent persistent cross-session memory with scope resolution."""
from __future__ import annotations

import time
from pathlib import Path


_MAX_LINES = 200
_MEMORY_FILENAME = "MEMORY.md"


class AgentMemoryScope:
    """Read/write per-agent memory at project or global scope.

    Scope resolution: project scope overrides global scope.
    Project scope: <project_dir>/.lidco/agent-memory/<name>/MEMORY.md
    Global scope:  <global_dir>/.lidco/agent-memory/<name>/MEMORY.md
    """

    def __init__(
        self,
        agent_name: str,
        project_dir: str | Path | None = None,
        global_dir: str | Path | None = None,
    ) -> None:
        self._name = agent_name
        self._project_dir = Path(project_dir) if project_dir else None
        self._global_dir = Path(global_dir) if global_dir else None

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def _project_path(self) -> Path | None:
        if self._project_dir is None:
            return None
        return self._project_dir / ".lidco" / "agent-memory" / self._name / _MEMORY_FILENAME

    def _global_path(self) -> Path | None:
        if self._global_dir is None:
            return None
        return self._global_dir / ".lidco" / "agent-memory" / self._name / _MEMORY_FILENAME

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load(self) -> str:
        """Load memory. Project scope first, then global, then ''."""
        for path in (self._project_path(), self._global_path()):
            if path is not None and path.exists():
                try:
                    lines = path.read_text(encoding="utf-8").splitlines()
                    return "\n".join(lines[:_MAX_LINES])
                except OSError:
                    continue
        return ""

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, content: str, use_global: bool = False) -> None:
        """Write content to project scope (or global scope if use_global=True)."""
        if use_global or self._project_dir is None:
            path = self._global_path()
        else:
            path = self._project_path()

        if path is None:
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        lines = content.splitlines()[:_MAX_LINES]
        path.write_text("\n".join(lines), encoding="utf-8")

    def append(self, entry: str) -> None:
        """Append a timestamped entry; trim to MAX_LINES."""
        existing = self.load()
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        new_entry = f"[{ts}] {entry}"

        lines = existing.splitlines() if existing else []
        lines.append(new_entry)

        # Trim from top if over limit
        if len(lines) > _MAX_LINES:
            lines = lines[len(lines) - _MAX_LINES:]

        self.save("\n".join(lines))

    def clear(self) -> None:
        """Delete the memory file for the active scope."""
        for path in (self._project_path(), self._global_path()):
            if path is not None and path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
