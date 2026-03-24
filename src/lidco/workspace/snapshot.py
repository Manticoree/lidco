"""WorkspaceSnapshotManager — snapshot + restore full workspace state."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WorkspaceSnapshot:
    id: str
    name: str
    timestamp: float
    files: dict[str, str]
    git_ref: str
    git_stash_ref: str
    history: list[dict]
    metadata: dict = field(default_factory=dict)


@dataclass
class RestoreResult:
    success: bool
    snapshot: WorkspaceSnapshot | None = None
    restored_files: list[str] = field(default_factory=list)
    error: str | None = None


_MAX_TOTAL_BYTES = 10 * 1024 * 1024  # 10 MB


class WorkspaceSnapshotManager:
    """Save and restore full workspace snapshots."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._project_dir = project_dir or Path.cwd()
        self._storage_dir = self._project_dir / ".lidco" / "workspace_snapshots"

    def _ensure_dir(self) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def _snapshot_path(self, snap_id: str) -> Path:
        return self._storage_dir / f"{snap_id}.json"

    def save(self, name: str, history: list[dict] | None = None, files: list[str] | None = None) -> WorkspaceSnapshot:
        """Snapshot modified files, git HEAD, and conversation history."""
        self._ensure_dir()

        # Read file contents
        file_contents: dict[str, str] = {}
        candidates = files or []
        if not candidates:
            # Collect all tracked modified files via git status porcelain (graceful fallback)
            try:
                import subprocess
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=self._project_dir,
                    capture_output=True,
                    text=True,
                )
                for line in result.stdout.splitlines():
                    if line.strip():
                        candidates.append(line[3:].strip())
            except Exception:
                pass

        for rel_path in candidates:
            abs_path = self._project_dir / rel_path
            if abs_path.is_file():
                try:
                    file_contents[rel_path] = abs_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass

        # Get git HEAD ref
        git_ref = ""
        git_stash_ref = ""
        try:
            import subprocess
            r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=self._project_dir, capture_output=True, text=True)
            git_ref = r.stdout.strip()
        except Exception:
            pass

        snap_id = str(uuid.uuid4())[:8]
        snap = WorkspaceSnapshot(
            id=snap_id,
            name=name,
            timestamp=time.time(),
            files=file_contents,
            git_ref=git_ref,
            git_stash_ref=git_stash_ref,
            history=list(history or []),
        )

        # Persist
        data = {
            "id": snap.id,
            "name": snap.name,
            "timestamp": snap.timestamp,
            "files": snap.files,
            "git_ref": snap.git_ref,
            "git_stash_ref": snap.git_stash_ref,
            "history": snap.history,
            "metadata": snap.metadata,
        }
        self._snapshot_path(snap_id).write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._enforce_size_limit()
        return snap

    def restore(self, name_or_id: str) -> RestoreResult:
        """Restore files from a named or ID'd snapshot."""
        snap = self._find(name_or_id)
        if snap is None:
            return RestoreResult(success=False, error=f"snapshot not found: {name_or_id}")

        restored = []
        for rel_path, content in snap.files.items():
            abs_path = self._project_dir / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(content, encoding="utf-8")
            restored.append(rel_path)

        return RestoreResult(success=True, snapshot=snap, restored_files=restored)

    def list(self) -> list[WorkspaceSnapshot]:
        if not self._storage_dir.exists():
            return []
        snaps = []
        for path in self._storage_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                snaps.append(WorkspaceSnapshot(**data))
            except Exception:
                pass
        return sorted(snaps, key=lambda s: s.timestamp, reverse=True)

    def delete(self, name_or_id: str) -> bool:
        snap = self._find(name_or_id)
        if snap is None:
            return False
        path = self._snapshot_path(snap.id)
        if path.exists():
            path.unlink()
            return True
        return False

    def _find(self, name_or_id: str) -> WorkspaceSnapshot | None:
        for snap in self.list():
            if snap.id == name_or_id or snap.name == name_or_id:
                return snap
        return None

    def _enforce_size_limit(self) -> None:
        """Remove oldest snapshots if total size exceeds 10 MB."""
        snaps = sorted(self.list(), key=lambda s: s.timestamp)
        total = sum(self._snapshot_path(s.id).stat().st_size for s in snaps if self._snapshot_path(s.id).exists())
        while total > _MAX_TOTAL_BYTES and snaps:
            oldest = snaps.pop(0)
            path = self._snapshot_path(oldest.id)
            if path.exists():
                total -= path.stat().st_size
                path.unlink()
