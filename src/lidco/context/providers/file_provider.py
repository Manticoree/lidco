"""File glob context provider."""
from __future__ import annotations

import glob as glob_module
from pathlib import Path

from .base import ContextProvider


class FileContextProvider(ContextProvider):
    """Reads files matching a glob pattern and injects their contents."""

    def __init__(
        self,
        name: str,
        pattern: str,
        base_dir: Path | None = None,
        priority: int = 50,
        max_tokens: int = 2000,
    ) -> None:
        super().__init__(name, priority, max_tokens)
        self._pattern = pattern
        self._base_dir = base_dir or Path.cwd()

    @property
    def pattern(self) -> str:
        return self._pattern

    async def fetch(self) -> str:
        parts = []
        matches = sorted(glob_module.glob(str(self._base_dir / self._pattern), recursive=True))
        for path_str in matches:
            path = Path(path_str)
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    rel = path.relative_to(self._base_dir)
                    parts.append(f"## {rel}\n{content}")
                except OSError:
                    pass
        return "\n\n".join(parts)
