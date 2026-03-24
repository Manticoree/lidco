"""WikiUpdater — incremental wiki regeneration on file change."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEBOUNCE_S = 30.0  # only update if file changed more than this many seconds ago


class WikiUpdater:
    """Watches changed files and regenerates wiki pages for modified modules."""

    def __init__(
        self,
        llm_client: Any | None = None,
        debounce_s: float = _DEBOUNCE_S,
    ) -> None:
        self._llm = llm_client
        self._debounce_s = debounce_s
        self._last_update: dict[str, float] = {}

    def update_on_change(self, changed_files: list[str], project_dir: Path) -> list[str]:
        """Regenerate wiki pages for *changed_files*.

        Returns list of updated wiki page paths.  Debounce: skips if the same
        file was updated within *debounce_s* seconds.
        """
        from lidco.wiki.generator import WikiGenerator
        gen = WikiGenerator(llm_client=self._llm)
        updated: list[str] = []
        now = time.time()

        for file_path in changed_files:
            p = Path(file_path)
            if not p.suffix == ".py":
                continue
            # Debounce check
            last = self._last_update.get(file_path, 0.0)
            if now - last < self._debounce_s:
                logger.debug("Debouncing wiki update for %s", file_path)
                continue
            try:
                page = gen.generate_module(file_path, project_dir)
                wiki_path = gen._wiki_path(file_path, project_dir)
                self._last_update[file_path] = now
                updated.append(str(wiki_path))
                logger.info("Wiki updated: %s", wiki_path)
            except Exception:
                logger.exception("Failed to update wiki for %s", file_path)

        return updated

    def force_update(self, file_path: str, project_dir: Path) -> str | None:
        """Force wiki regeneration for *file_path*, bypassing debounce."""
        self._last_update.pop(file_path, None)
        results = self.update_on_change([file_path], project_dir)
        return results[0] if results else None
