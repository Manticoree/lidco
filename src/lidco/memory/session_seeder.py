"""SessionSeeder — pre-populate a new session with relevant memories."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class SeedContext:
    memories: list  # list[AgentMemory]
    prompt_block: str
    token_estimate: int
    source: str  # "workspace" | "global" | "both"


class SessionSeeder:
    """Seed a new session with memories from TieredMemoryStore."""

    def __init__(
        self,
        memory_store: object,
        token_budget: int = 2048,
        tags_filter: list[str] | None = None,
    ) -> None:
        self._store = memory_store
        self.token_budget = token_budget
        self.tags_filter = tags_filter or []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def seed(
        self,
        project_name: str = "",
        recent_files: list[str] | None = None,
    ) -> SeedContext:
        """Query memory and build a SeedContext for session injection."""
        ws_store = getattr(self._store, "workspace_store", None)
        global_store = getattr(self._store, "global_store", None)

        ws_memories: list = []
        global_memories: list = []

        # Query workspace store
        if ws_store is not None:
            query = project_name or ""
            try:
                ws_memories = ws_store.search(query, limit=20) or []
            except Exception:
                ws_memories = []

            # Also search for recent files
            if recent_files:
                seen_ids = {getattr(m, "id", None) for m in ws_memories}
                for rf in recent_files:
                    try:
                        extras = ws_store.search(rf, limit=5) or []
                        for m in extras:
                            mid = getattr(m, "id", None)
                            if mid not in seen_ids:
                                ws_memories.append(m)
                                seen_ids.add(mid)
                    except Exception:
                        pass

        # Query global store
        if global_store is not None:
            query = project_name or ""
            try:
                global_memories = global_store.search(query, limit=20) or []
            except Exception:
                global_memories = []

            if recent_files:
                seen_ids = {getattr(m, "id", None) for m in global_memories}
                for rf in recent_files:
                    try:
                        extras = global_store.search(rf, limit=5) or []
                        for m in extras:
                            mid = getattr(m, "id", None)
                            if mid not in seen_ids:
                                global_memories.append(m)
                                seen_ids.add(mid)
                    except Exception:
                        pass

        # Deduplicate by content (workspace first)
        seen_content: set[str] = set()
        combined: list = []
        for m in ws_memories:
            content = getattr(m, "content", "")
            if content not in seen_content:
                combined.append(m)
                seen_content.add(content)

        global_only: list = []
        for m in global_memories:
            content = getattr(m, "content", "")
            if content not in seen_content:
                global_only.append(m)
                seen_content.add(content)
                combined.append(m)

        # Apply tags filter
        if self.tags_filter:
            filtered: list = []
            for m in combined:
                tags = getattr(m, "tags", []) or []
                if any(t in tags for t in self.tags_filter):
                    filtered.append(m)
            combined = filtered

        # Determine source
        has_ws = len(ws_memories) > 0
        has_global = len(global_only) > 0 or (not has_ws and len(global_memories) > 0)

        if has_ws and (has_global or len(global_only) > 0):
            source = "both"
        elif has_ws:
            source = "workspace"
        else:
            source = "global"

        prompt_block = self.format_memories(combined, self.token_budget)
        token_est = len(prompt_block) // 4

        return SeedContext(
            memories=combined,
            prompt_block=prompt_block,
            token_estimate=token_est,
            source=source,
        )

    def format_memories(self, memories: list, budget: int) -> str:
        """Format memories as a markdown block, truncated at budget tokens."""
        if not memories:
            return ""

        char_budget = budget * 4
        header = "## Memory\n"
        lines: list[str] = [header]
        used = len(header)

        for m in memories:
            content = getattr(m, "content", str(m))
            line = f"- {content}\n"
            if used + len(line) > char_budget:
                break
            lines.append(line)
            used += len(line)

        return "".join(lines)

    def should_seed(self) -> bool:
        """Return True if the memory store has any entries."""
        try:
            results = self._store.search("", limit=1)
            return bool(results)
        except Exception:
            return False
