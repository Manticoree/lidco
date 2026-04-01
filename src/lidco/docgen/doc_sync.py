"""Doc Sync — detect stale documentation relative to source changes."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class StaleDoc:
    """A documentation file that may be out of date."""

    path: str
    reason: str
    last_code_change: str
    last_doc_change: str


@dataclass(frozen=True)
class SyncStatus:
    """Overall documentation sync status."""

    total_docs: int
    stale: int
    fresh: int
    stale_docs: tuple[StaleDoc, ...]


class DocSyncEngine:
    """Check documentation freshness against source code.

    Parameters
    ----------
    project_path:
        Root path of the project.
    """

    def __init__(self, project_path: str) -> None:
        self._project_path = project_path

    def check_staleness(self) -> SyncStatus:
        """Check all docs against source for staleness."""
        docs_dir = os.path.join(self._project_path, "docs")
        src_dir = os.path.join(self._project_path, "src")
        stale_list = self.find_stale(docs_dir, src_dir)
        total = self._count_docs(docs_dir)
        stale_count = len(stale_list)
        return SyncStatus(
            total_docs=total,
            stale=stale_count,
            fresh=total - stale_count,
            stale_docs=stale_list,
        )

    def find_stale(
        self, docs_dir: str, src_dir: str
    ) -> tuple[StaleDoc, ...]:
        """Find documentation files older than corresponding source files."""
        stale: list[StaleDoc] = []
        if not os.path.isdir(docs_dir):
            return ()
        latest_src_mtime = self._latest_mtime(src_dir)
        if latest_src_mtime <= 0:
            return ()
        latest_src_str = time.strftime(
            "%Y-%m-%dT%H:%M:%S", time.localtime(latest_src_mtime)
        )
        for root, _dirs, files in os.walk(docs_dir):
            for fname in files:
                if not fname.endswith((".md", ".rst", ".txt")):
                    continue
                doc_path = os.path.join(root, fname)
                try:
                    doc_mtime = os.path.getmtime(doc_path)
                except OSError:
                    continue
                doc_str = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(doc_mtime)
                )
                if doc_mtime < latest_src_mtime:
                    stale.append(
                        StaleDoc(
                            path=doc_path,
                            reason="doc older than latest source change",
                            last_code_change=latest_src_str,
                            last_doc_change=doc_str,
                        )
                    )
        return tuple(stale)

    def _count_docs(self, docs_dir: str) -> int:
        count = 0
        if not os.path.isdir(docs_dir):
            return 0
        for _root, _dirs, files in os.walk(docs_dir):
            for f in files:
                if f.endswith((".md", ".rst", ".txt")):
                    count += 1
        return count

    def _latest_mtime(self, src_dir: str) -> float:
        latest = 0.0
        if not os.path.isdir(src_dir):
            return 0.0
        for root, _dirs, files in os.walk(src_dir):
            for f in files:
                if f.endswith(".py"):
                    try:
                        mt = os.path.getmtime(os.path.join(root, f))
                        if mt > latest:
                            latest = mt
                    except OSError:
                        continue
        return latest


__all__ = ["StaleDoc", "SyncStatus", "DocSyncEngine"]
