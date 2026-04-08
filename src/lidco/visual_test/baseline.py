"""Baseline Manager — store/update baselines, per-branch baselines,
approval workflow, and auto-update on merge."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---- Data classes --------------------------------------------------------


@dataclass(frozen=True)
class BaselineEntry:
    """A single stored baseline."""

    name: str
    branch: str
    sha256: str
    width: int
    height: int
    created_at: float
    approved: bool = True
    approved_by: str = ""


@dataclass(frozen=True)
class ApprovalRequest:
    """A pending request to update a baseline."""

    name: str
    branch: str
    old_sha256: str
    new_sha256: str
    requested_at: float
    diff_percentage: float = 0.0


@dataclass(frozen=True)
class MergeResult:
    """Summary of baselines auto-updated on merge."""

    merged_count: int
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---- BaselineManager -----------------------------------------------------


class BaselineManager:
    """Manage visual regression baselines with per-branch support and approval."""

    def __init__(self, storage_dir: str | Path = ".lidco/baselines") -> None:
        self._storage_dir = Path(storage_dir)
        self._entries: dict[str, BaselineEntry] = {}
        self._pending: list[ApprovalRequest] = []
        self._load_index()

    # -- properties --------------------------------------------------------

    @property
    def storage_dir(self) -> Path:
        return self._storage_dir

    @property
    def entries(self) -> dict[str, BaselineEntry]:
        return dict(self._entries)

    @property
    def pending_approvals(self) -> list[ApprovalRequest]:
        return list(self._pending)

    # -- public API --------------------------------------------------------

    def store(
        self, name: str, branch: str, image_bytes: bytes,
        width: int, height: int, *, auto_approve: bool = True,
    ) -> BaselineEntry:
        """Store or update a baseline image. Returns the new entry."""
        sha = hashlib.sha256(image_bytes).hexdigest()
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        key = self._key(name, branch)

        img_path = self._image_path(name, branch)
        img_path.write_bytes(image_bytes)

        entry = BaselineEntry(
            name=name, branch=branch, sha256=sha,
            width=width, height=height,
            created_at=time.time(), approved=auto_approve,
        )
        self._entries = {**self._entries, key: entry}
        self._save_index()
        return entry

    def get(self, name: str, branch: str) -> BaselineEntry | None:
        """Retrieve a baseline entry by name and branch."""
        return self._entries.get(self._key(name, branch))

    def get_image(self, name: str, branch: str) -> bytes | None:
        """Read the baseline image bytes from disk."""
        p = self._image_path(name, branch)
        if p.exists():
            return p.read_bytes()
        return None

    def delete(self, name: str, branch: str) -> bool:
        """Delete a baseline. Returns True if it existed."""
        key = self._key(name, branch)
        if key not in self._entries:
            return False
        self._entries = {k: v for k, v in self._entries.items() if k != key}
        img_path = self._image_path(name, branch)
        if img_path.exists():
            img_path.unlink()
        self._save_index()
        return True

    def list_baselines(self, branch: str | None = None) -> list[BaselineEntry]:
        """List baselines, optionally filtered by branch."""
        entries = list(self._entries.values())
        if branch is not None:
            entries = [e for e in entries if e.branch == branch]
        return sorted(entries, key=lambda e: e.name)

    def request_approval(
        self, name: str, branch: str, new_sha256: str, diff_percentage: float = 0.0,
    ) -> ApprovalRequest:
        """Create a pending approval request for a baseline update."""
        old = self._entries.get(self._key(name, branch))
        old_sha = old.sha256 if old else ""
        req = ApprovalRequest(
            name=name, branch=branch, old_sha256=old_sha,
            new_sha256=new_sha256, requested_at=time.time(),
            diff_percentage=diff_percentage,
        )
        self._pending = [*self._pending, req]
        return req

    def approve(self, name: str, branch: str, approved_by: str = "") -> bool:
        """Approve a pending baseline update. Returns True if found and approved."""
        matching = [r for r in self._pending if r.name == name and r.branch == branch]
        if not matching:
            return False
        self._pending = [r for r in self._pending if not (r.name == name and r.branch == branch)]
        key = self._key(name, branch)
        existing = self._entries.get(key)
        if existing is not None:
            updated = BaselineEntry(
                name=existing.name, branch=existing.branch,
                sha256=matching[0].new_sha256,
                width=existing.width, height=existing.height,
                created_at=time.time(), approved=True,
                approved_by=approved_by,
            )
            self._entries = {**self._entries, key: updated}
            self._save_index()
        return True

    def reject(self, name: str, branch: str) -> bool:
        """Reject a pending approval. Returns True if found."""
        before = len(self._pending)
        self._pending = [r for r in self._pending if not (r.name == name and r.branch == branch)]
        return len(self._pending) < before

    def merge_baselines(self, source_branch: str, target_branch: str) -> MergeResult:
        """Copy approved baselines from source to target branch."""
        source = [e for e in self._entries.values() if e.branch == source_branch and e.approved]
        merged = 0
        skipped: list[str] = []
        errors: list[str] = []

        for entry in source:
            src_img = self._image_path(entry.name, source_branch)
            if not src_img.exists():
                errors = [*errors, f"Image missing for {entry.name}"]
                continue

            img_data = src_img.read_bytes()
            target_key = self._key(entry.name, target_branch)
            existing = self._entries.get(target_key)
            if existing and existing.sha256 == entry.sha256:
                skipped = [*skipped, entry.name]
                continue

            self.store(
                entry.name, target_branch, img_data,
                entry.width, entry.height, auto_approve=True,
            )
            merged += 1

        return MergeResult(merged_count=merged, skipped=skipped, errors=errors)

    # -- private -----------------------------------------------------------

    @staticmethod
    def _key(name: str, branch: str) -> str:
        return f"{branch}:{name}"

    def _image_path(self, name: str, branch: str) -> Path:
        safe_branch = branch.replace("/", "__")
        return self._storage_dir / f"{safe_branch}_{name}.png"

    def _index_path(self) -> Path:
        return self._storage_dir / "index.json"

    def _save_index(self) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        data = {}
        for key, entry in self._entries.items():
            data[key] = {
                "name": entry.name, "branch": entry.branch,
                "sha256": entry.sha256, "width": entry.width,
                "height": entry.height, "created_at": entry.created_at,
                "approved": entry.approved, "approved_by": entry.approved_by,
            }
        self._index_path().write_text(json.dumps(data, indent=2))

    def _load_index(self) -> None:
        p = self._index_path()
        if not p.exists():
            return
        try:
            raw = json.loads(p.read_text())
            for key, val in raw.items():
                self._entries = {
                    **self._entries,
                    key: BaselineEntry(**val),
                }
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
