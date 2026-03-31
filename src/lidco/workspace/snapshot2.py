"""Workspace snapshot manager — Q127."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class FileSnapshot:
    path: str
    content: str
    mtime: float = 0.0
    size: int = 0


@dataclass
class WorkspaceSnapshot:
    id: str
    label: str
    created_at: str
    files: dict[str, "FileSnapshot"] = field(default_factory=dict)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.files.values())


class WorkspaceSnapshotManager:
    """Capture and restore workspace file snapshots."""

    def __init__(
        self,
        read_fn: Callable[[str], str] = None,
        write_fn: Callable[[str, str], None] = None,
    ) -> None:
        self._read_fn = read_fn
        self._write_fn = write_fn

    def _read(self, path: str) -> Optional[str]:
        if self._read_fn is not None:
            return self._read_fn(path)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return None

    def _write(self, path: str, content: str) -> None:
        if self._write_fn is not None:
            self._write_fn(path, content)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

    def capture(self, paths: list[str], label: str = "") -> WorkspaceSnapshot:
        snap_id = str(uuid.uuid4())[:8]
        created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        files: dict[str, FileSnapshot] = {}
        for p in paths:
            content = self._read(p)
            if content is not None:
                files[p] = FileSnapshot(
                    path=p,
                    content=content,
                    mtime=time.time(),
                    size=len(content.encode("utf-8")),
                )
        return WorkspaceSnapshot(
            id=snap_id,
            label=label,
            created_at=created_at,
            files=files,
        )

    def restore(self, snapshot: WorkspaceSnapshot, dry_run: bool = False) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for path, fs in snapshot.files.items():
            if dry_run:
                results[path] = True
                continue
            try:
                self._write(path, fs.content)
                results[path] = True
            except Exception:
                results[path] = False
        return results

    def diff(
        self,
        snap_a: WorkspaceSnapshot,
        snap_b: WorkspaceSnapshot,
    ) -> dict:
        keys_a = set(snap_a.files)
        keys_b = set(snap_b.files)
        added = sorted(keys_b - keys_a)
        removed = sorted(keys_a - keys_b)
        modified = []
        unchanged = []
        for k in sorted(keys_a & keys_b):
            if snap_a.files[k].content != snap_b.files[k].content:
                modified.append(k)
            else:
                unchanged.append(k)
        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "unchanged": unchanged,
        }

    def save(self, snapshot: WorkspaceSnapshot, store_path: str) -> None:
        data = {
            "id": snapshot.id,
            "label": snapshot.label,
            "created_at": snapshot.created_at,
            "files": {
                k: {
                    "path": v.path,
                    "content": v.content,
                    "mtime": v.mtime,
                    "size": v.size,
                }
                for k, v in snapshot.files.items()
            },
        }
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self, store_path: str) -> WorkspaceSnapshot:
        with open(store_path, encoding="utf-8") as f:
            data = json.load(f)
        files = {
            k: FileSnapshot(**v)
            for k, v in data.get("files", {}).items()
        }
        return WorkspaceSnapshot(
            id=data["id"],
            label=data["label"],
            created_at=data["created_at"],
            files=files,
        )
