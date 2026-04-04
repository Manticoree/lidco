"""DocSync — synchronize local markdown files with Notion pages."""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field

from lidco.notion.client import NotionClient


@dataclass
class SyncResult:
    """Result of a single file sync operation."""

    path: str
    status: str  # "created" | "updated" | "unchanged" | "error"
    page_id: str | None = None
    message: str = ""
    timestamp: float = field(default_factory=time.time)


class DocSync:
    """Sync local markdown files to/from a simulated Notion workspace.

    Parameters
    ----------
    client:
        The :class:`NotionClient` to use for page operations.
    parent_id:
        Parent page/database ID under which synced pages are created.
    """

    def __init__(self, client: NotionClient, parent_id: str | None = None) -> None:
        self._client = client
        self._parent_id = parent_id
        # path -> (page_id, content_hash, timestamp)
        self._sync_map: dict[str, tuple[str, str, float]] = {}

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    # --------------------------------------------------------- single file

    def sync_file(self, path: str) -> SyncResult:
        """Sync a single markdown file to Notion.

        If the file has been synced before and content is unchanged, returns
        status ``"unchanged"``.  Otherwise creates or updates the page.

        Raises
        ------
        FileNotFoundError
            If *path* does not exist on disk.
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"File not found: {path}")

        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()

        content_hash = self._hash(content)
        title = os.path.splitext(os.path.basename(path))[0]

        if path in self._sync_map:
            page_id, old_hash, _ts = self._sync_map[path]
            if content_hash == old_hash:
                return SyncResult(
                    path=path, status="unchanged", page_id=page_id,
                    message="Content unchanged since last sync",
                )
            try:
                self._client.update_page(page_id, title=title, content=content)
            except KeyError:
                # Page was deleted remotely; recreate
                page = self._client.create_page(self._parent_id, title, content)
                page_id = page.id
            now = time.time()
            self._sync_map[path] = (page_id, content_hash, now)
            return SyncResult(path=path, status="updated", page_id=page_id, message="Page updated")

        page = self._client.create_page(self._parent_id, title, content)
        now = time.time()
        self._sync_map[path] = (page.id, content_hash, now)
        return SyncResult(path=path, status="created", page_id=page.id, message="Page created")

    # -------------------------------------------------------- directory

    def sync_all(self, directory: str) -> list[SyncResult]:
        """Sync all ``.md`` files in *directory* (non-recursive).

        Returns a list of :class:`SyncResult` for each file.

        Raises
        ------
        NotADirectoryError
            If *directory* is not a valid directory.
        """
        if not os.path.isdir(directory):
            raise NotADirectoryError(f"Not a directory: {directory}")

        results: list[SyncResult] = []
        for name in sorted(os.listdir(directory)):
            if name.lower().endswith(".md"):
                full = os.path.join(directory, name)
                try:
                    results.append(self.sync_file(full))
                except Exception as exc:  # noqa: BLE001
                    results.append(SyncResult(
                        path=full, status="error", message=str(exc),
                    ))
        return results

    # --------------------------------------------------- conflict resolution

    @staticmethod
    def conflict_resolution(local: str, remote: str) -> str:
        """Resolve a conflict between *local* and *remote* content.

        Strategy: local wins, but remote-only lines are appended under a
        ``## Remote additions`` heading.
        """
        local_lines = set(local.splitlines())
        remote_lines = remote.splitlines()
        remote_only = [ln for ln in remote_lines if ln not in local_lines]
        if not remote_only:
            return local
        return local.rstrip("\n") + "\n\n## Remote additions\n" + "\n".join(remote_only) + "\n"

    # ----------------------------------------------------------- metadata

    def last_sync(self, path: str) -> float:
        """Return the timestamp of the last sync for *path*, or ``0.0``."""
        if path in self._sync_map:
            return self._sync_map[path][2]
        return 0.0
