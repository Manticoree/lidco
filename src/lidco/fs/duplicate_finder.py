"""Q132: Find duplicate files by content hash."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class DuplicateGroup:
    content_hash: str
    paths: list[str]
    size: int  # size in bytes of one copy

    @property
    def wasted_bytes(self) -> int:
        return (len(self.paths) - 1) * self.size


class DuplicateFinder:
    """Group files by content hash and report duplicates."""

    def __init__(self, hash_fn: Callable[[str], str] | None = None) -> None:
        self._hash_fn = hash_fn or self._sha256

    def find(self, files: dict[str, str]) -> list[DuplicateGroup]:
        """Find duplicate files.

        *files* maps path → content (as str or bytes-like).
        Returns groups with 2+ paths.
        """
        buckets: dict[str, list[str]] = {}
        sizes: dict[str, int] = {}

        for path, content in files.items():
            h = self._hash_fn(content)
            buckets.setdefault(h, []).append(path)
            sizes.setdefault(h, len(content.encode() if isinstance(content, str) else content))

        groups: list[DuplicateGroup] = []
        for h, paths in buckets.items():
            if len(paths) >= 2:
                groups.append(
                    DuplicateGroup(
                        content_hash=h,
                        paths=sorted(paths),
                        size=sizes[h],
                    )
                )

        groups.sort(key=lambda g: g.size, reverse=True)
        return groups

    def summary(self, groups: list[DuplicateGroup]) -> dict:
        total_wasted = sum(g.wasted_bytes for g in groups)
        files_involved = sum(len(g.paths) for g in groups)
        return {
            "groups": len(groups),
            "total_wasted_bytes": total_wasted,
            "files_involved": files_involved,
        }

    # --- internals -----------------------------------------------------------

    @staticmethod
    def _sha256(content: str | bytes) -> str:
        if isinstance(content, str):
            content = content.encode()
        return hashlib.sha256(content).hexdigest()
