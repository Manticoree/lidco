"""RepoMapInjector — prepend ranked repo map (and optional memory seed) to LLM messages."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.context.repo_map import RepoMap
    from lidco.memory.session_seeder import SessionSeeder


class RepoMapInjector:
    """Inject a repository-map context block into the system message."""

    def __init__(
        self,
        repo_map: object,
        session_seeder: object | None = None,
        enabled: bool = True,
    ) -> None:
        self._repo_map = repo_map
        self._session_seeder = session_seeder
        self._enabled = enabled

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inject(
        self,
        messages: list[dict],
        changed_files: list[str] | None = None,
    ) -> list[dict]:
        """Return a new message list with the context block prepended to the system message."""
        if not self._enabled:
            return messages

        block = self.build_context_block(changed_files)
        if not block:
            return messages

        # Find first system message
        system_idx: int | None = None
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                system_idx = i
                break

        new_messages: list[dict] = list(messages)

        if system_idx is not None:
            original = new_messages[system_idx]
            new_content = block + "\n\n" + original.get("content", "")
            new_messages = (
                new_messages[:system_idx]
                + [{**original, "content": new_content}]
                + new_messages[system_idx + 1 :]
            )
        else:
            new_messages = [{"role": "system", "content": block}] + new_messages

        return new_messages

    def toggle(self) -> bool:
        """Flip enabled flag and return new state."""
        self._enabled = not self._enabled
        return self._enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def build_context_block(self, changed_files: list[str] | None = None) -> str:
        """Build the context block string from repo map and optional memory seed."""
        try:
            repo_map_str = self._repo_map.generate(changed_files)
        except Exception:
            repo_map_str = ""

        if self._session_seeder is not None:
            try:
                seed = self._session_seeder.seed()
                memory_block = seed.prompt_block
            except Exception:
                memory_block = ""
            return (
                f"## Repository Context\n{repo_map_str}\n\n## Memory\n{memory_block}"
            )

        return f"## Repository Context\n{repo_map_str}"

    def estimate_tokens(self, block: str) -> int:
        return len(block) // 4
