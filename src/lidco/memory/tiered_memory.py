"""TieredMemoryStore — workspace-scoped vs. global memory hierarchy."""
from __future__ import annotations

from pathlib import Path

from .agent_memory import AgentMemory, AgentMemoryStore


class TieredMemoryStore:
    """Two-tier memory: workspace (local) and global (~/.lidco/)."""

    def __init__(
        self,
        project_dir: Path | None = None,
        global_dir: Path | None = None,
    ) -> None:
        project_dir = project_dir or Path.cwd()
        global_dir = global_dir or Path.home() / ".lidco"
        self._workspace = AgentMemoryStore(db_path=project_dir / ".lidco" / "agent_memory.db")
        self._global = AgentMemoryStore(db_path=global_dir / "global_memory.db")

    @property
    def workspace_store(self) -> AgentMemoryStore:
        return self._workspace

    @property
    def global_store(self) -> AgentMemoryStore:
        return self._global

    def add(self, content: str, tags: list[str] | None = None, scope: str = "workspace") -> AgentMemory:
        """Add memory to workspace (default) or global scope."""
        if scope == "global":
            return self._global.add(content, tags or [])
        return self._workspace.add(content, tags or [])

    def search(self, query: str, limit: int = 10) -> list[AgentMemory]:
        """Search both stores; workspace results ranked above global."""
        ws_results = self._workspace.search(query, limit=limit)
        global_results = self._global.search(query, limit=limit)
        # Workspace first, deduplicate by content
        seen = {m.content for m in ws_results}
        combined = list(ws_results)
        for m in global_results:
            if m.content not in seen:
                combined.append(m)
                seen.add(m.content)
        return combined[:limit]

    def list(self, limit: int = 20) -> list[AgentMemory]:
        ws = self._workspace.list(limit=limit)
        gl = self._global.list(limit=limit)
        return ws + gl

    def delete(self, memory_id: str) -> bool:
        return self._workspace.delete(memory_id) or self._global.delete(memory_id)

    def format_context(self) -> str:
        """Format memories for injection as context."""
        ws = self._workspace.list(limit=10)
        gl = self._global.list(limit=10)
        parts = []
        if ws:
            parts.append("## Workspace memories\n" + "\n".join(f"- {m.content}" for m in ws))
        if gl:
            parts.append("## Global memories\n" + "\n".join(f"- {m.content}" for m in gl))
        return "\n\n".join(parts)
