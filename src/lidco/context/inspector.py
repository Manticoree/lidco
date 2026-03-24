"""ContextInspector — transparent view of the LLM request context window."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextSection:
    name: str
    content: str
    token_estimate: int
    source: str  # "system" | "memory" | "rules" | "history" | "tools" | "pinned"


@dataclass
class ContextSnapshot:
    sections: list[ContextSection]
    total_tokens: int
    model_limit: int
    session_id: str
    timestamp: float


class ContextInspector:
    """Inspect, edit, and augment the context window of a session."""

    DEFAULT_MODEL_LIMIT = 200_000

    def __init__(self, session: Any = None) -> None:
        self._session = session
        self._pinned: list[ContextSection] = []
        self._dropped: set[str] = set()

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self) -> ContextSnapshot:
        """Build a ContextSnapshot from the current session state."""
        sections = self._extract_sections()
        # Add pinned sections
        sections.extend(self._pinned)
        # Remove dropped sections
        sections = [s for s in sections if s.name not in self._dropped]

        total = sum(s.token_estimate for s in sections)
        limit = self._get_model_limit()

        return ContextSnapshot(
            sections=sections,
            total_tokens=total,
            model_limit=limit,
            session_id=self._get_session_id(),
            timestamp=time.time(),
        )

    def _extract_sections(self) -> list[ContextSection]:
        """Extract sections from the session object (or return stubs)."""
        if self._session is None:
            return []

        sections: list[ContextSection] = []

        # System prompt
        sys_prompt = ""
        if hasattr(self._session, "system_prompt"):
            sys_prompt = str(self._session.system_prompt or "")
        if sys_prompt:
            sections.append(ContextSection(
                name="system",
                content=sys_prompt,
                token_estimate=len(sys_prompt) // 4,
                source="system",
            ))

        # Memory / rules
        for attr, source in [("memory_content", "memory"), ("rules_content", "rules")]:
            val = getattr(self._session, attr, "")
            if val:
                sections.append(ContextSection(
                    name=source,
                    content=str(val),
                    token_estimate=len(str(val)) // 4,
                    source=source,
                ))

        # Conversation history
        history = getattr(self._session, "messages", None) or []
        history_text = "\n".join(
            f"{m.get('role','?')}: {str(m.get('content',''))[:200]}"
            for m in history
        )
        if history_text:
            sections.append(ContextSection(
                name="history",
                content=history_text,
                token_estimate=len(history_text) // 4,
                source="history",
            ))

        # Tool results
        tool_results = getattr(self._session, "tool_results", None) or []
        for i, tr in enumerate(tool_results):
            content = str(tr)
            sections.append(ContextSection(
                name=f"tool_result_{i}",
                content=content,
                token_estimate=len(content) // 4,
                source="tools",
            ))

        return sections

    def _get_model_limit(self) -> int:
        if self._session and hasattr(self._session, "model_limit"):
            return int(self._session.model_limit)
        return self.DEFAULT_MODEL_LIMIT

    def _get_session_id(self) -> str:
        if self._session and hasattr(self._session, "session_id"):
            return str(self._session.session_id)
        return "unknown"

    # ------------------------------------------------------------------
    # Format
    # ------------------------------------------------------------------

    def format_summary(self) -> str:
        """Return a human-readable breakdown of context sections."""
        snap = self.snapshot()
        pct_used = (snap.total_tokens / snap.model_limit * 100) if snap.model_limit else 0
        lines = [
            f"Context Window: {snap.total_tokens:,} / {snap.model_limit:,} tokens ({pct_used:.1f}% used)",
            "",
            "Sections:",
        ]
        for s in snap.sections:
            pct = (s.token_estimate / snap.total_tokens * 100) if snap.total_tokens else 0
            lines.append(f"  [{s.source:8}] {s.name:<24} {s.token_estimate:>6} tokens ({pct:.1f}%)")

        if not snap.sections:
            lines.append("  (no sections)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def drop(self, section_name: str) -> bool:
        """Remove a section from future snapshots. Returns True if it existed."""
        snap = self.snapshot()
        exists = any(s.name == section_name for s in snap.sections)
        if exists:
            self._dropped.add(section_name)
        return exists

    def pin(self, text: str, label: str = "pinned") -> None:
        """Inject arbitrary text as a high-priority pinned context section."""
        section = ContextSection(
            name=label,
            content=text,
            token_estimate=len(text) // 4,
            source="pinned",
        )
        self._pinned = [*self._pinned, section]

    def pinned_sections(self) -> list[ContextSection]:
        """Return all currently pinned sections."""
        return list(self._pinned)
