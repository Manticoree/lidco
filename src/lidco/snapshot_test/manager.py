"""
Snapshot Manager — create/update snapshots, serialization, per-test naming, directory structure.

Task 1677.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SnapshotMeta:
    """Metadata stored alongside each snapshot."""

    name: str
    created_at: float
    updated_at: float
    content_hash: str
    size_bytes: int
    format: str = "json"


@dataclass(frozen=True)
class SnapshotRecord:
    """A snapshot file record: content + metadata."""

    name: str
    content: str
    meta: SnapshotMeta
    path: str


class SnapshotManager:
    """Manage snapshot files: create, read, update, delete, list."""

    SNAP_DIR = "__snapshots__"
    META_SUFFIX = ".meta.json"
    SNAP_SUFFIX = ".snap"

    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir)
        self._snap_dir = self._base_dir / self.SNAP_DIR
        self._snap_dir.mkdir(parents=True, exist_ok=True)

    @property
    def snapshot_dir(self) -> Path:
        return self._snap_dir

    # ------------------------------------------------------------------
    # Naming helpers
    # ------------------------------------------------------------------

    @staticmethod
    def make_name(test_file: str, test_name: str, index: int = 0) -> str:
        """Build a deterministic snapshot name from test identity."""
        base = f"{test_file}__{test_name}"
        if index > 0:
            base = f"{base}__{index}"
        # sanitise
        return base.replace("/", "_").replace("\\", "_").replace(" ", "_")

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def serialize(value: Any) -> str:
        """Serialize a value to a stable string representation."""
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        try:
            return json.dumps(value, indent=2, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return repr(value)

    @staticmethod
    def _content_hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _snap_path(self, name: str) -> Path:
        return self._snap_dir / f"{name}{self.SNAP_SUFFIX}"

    def _meta_path(self, name: str) -> Path:
        return self._snap_dir / f"{name}{self.META_SUFFIX}"

    def create(self, name: str, value: Any) -> SnapshotRecord:
        """Create or overwrite a snapshot."""
        content = self.serialize(value)
        now = time.time()
        h = self._content_hash(content)

        meta = SnapshotMeta(
            name=name,
            created_at=now,
            updated_at=now,
            content_hash=h,
            size_bytes=len(content.encode()),
        )

        snap_p = self._snap_path(name)
        snap_p.write_text(content, encoding="utf-8")
        self._meta_path(name).write_text(
            json.dumps(
                {
                    "name": meta.name,
                    "created_at": meta.created_at,
                    "updated_at": meta.updated_at,
                    "content_hash": meta.content_hash,
                    "size_bytes": meta.size_bytes,
                    "format": meta.format,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return SnapshotRecord(name=name, content=content, meta=meta, path=str(snap_p))

    def read(self, name: str) -> SnapshotRecord | None:
        """Read a snapshot by name. Returns *None* if it doesn't exist."""
        snap_p = self._snap_path(name)
        if not snap_p.exists():
            return None
        content = snap_p.read_text(encoding="utf-8")
        meta = self._load_meta(name)
        return SnapshotRecord(name=name, content=content, meta=meta, path=str(snap_p))

    def update(self, name: str, value: Any) -> SnapshotRecord:
        """Update an existing snapshot. Creates if missing."""
        existing = self.read(name)
        content = self.serialize(value)
        now = time.time()
        h = self._content_hash(content)
        created = existing.meta.created_at if existing else now

        meta = SnapshotMeta(
            name=name,
            created_at=created,
            updated_at=now,
            content_hash=h,
            size_bytes=len(content.encode()),
        )

        self._snap_path(name).write_text(content, encoding="utf-8")
        self._meta_path(name).write_text(
            json.dumps(
                {
                    "name": meta.name,
                    "created_at": meta.created_at,
                    "updated_at": meta.updated_at,
                    "content_hash": meta.content_hash,
                    "size_bytes": meta.size_bytes,
                    "format": meta.format,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return SnapshotRecord(name=name, content=content, meta=meta, path=str(self._snap_path(name)))

    def delete(self, name: str) -> bool:
        """Delete a snapshot. Returns True if it existed."""
        snap_p = self._snap_path(name)
        meta_p = self._meta_path(name)
        existed = snap_p.exists()
        if snap_p.exists():
            snap_p.unlink()
        if meta_p.exists():
            meta_p.unlink()
        return existed

    def list_snapshots(self) -> list[str]:
        """Return sorted list of snapshot names."""
        names: list[str] = []
        for p in sorted(self._snap_dir.iterdir()):
            if p.name.endswith(self.SNAP_SUFFIX):
                names.append(p.name[: -len(self.SNAP_SUFFIX)])
        return names

    def exists(self, name: str) -> bool:
        return self._snap_path(name).exists()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_meta(self, name: str) -> SnapshotMeta:
        meta_p = self._meta_path(name)
        if meta_p.exists():
            data = json.loads(meta_p.read_text(encoding="utf-8"))
            return SnapshotMeta(**data)
        # fallback from file stats
        snap_p = self._snap_path(name)
        content = snap_p.read_text(encoding="utf-8")
        st = snap_p.stat()
        return SnapshotMeta(
            name=name,
            created_at=st.st_ctime,
            updated_at=st.st_mtime,
            content_hash=self._content_hash(content),
            size_bytes=len(content.encode()),
        )
