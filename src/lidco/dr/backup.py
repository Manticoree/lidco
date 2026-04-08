"""
Backup Manager -- automated backups with incremental, versioned, encrypted,
multi-destination support and retention policies.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class BackupType(Enum):
    """Type of backup."""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(Enum):
    """Status of a backup operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DestinationType(Enum):
    """Backup destination type."""

    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"


@dataclass(frozen=True)
class RetentionPolicy:
    """Retention policy for backup versions."""

    max_versions: int = 10
    max_age_days: int = 90
    min_versions: int = 1

    def __post_init__(self) -> None:
        if self.max_versions < 1:
            raise ValueError("max_versions must be >= 1")
        if self.max_age_days < 1:
            raise ValueError("max_age_days must be >= 1")
        if self.min_versions < 1:
            raise ValueError("min_versions must be >= 1")
        if self.min_versions > self.max_versions:
            raise ValueError("min_versions must be <= max_versions")


@dataclass(frozen=True)
class BackupDestination:
    """A backup destination configuration."""

    destination_type: DestinationType
    path: str
    credentials: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("path must not be empty")


@dataclass(frozen=True)
class EncryptionConfig:
    """Encryption configuration for backups."""

    enabled: bool = False
    algorithm: str = "aes-256-cbc"
    key_id: str = ""

    def __post_init__(self) -> None:
        if self.enabled and not self.key_id:
            raise ValueError("key_id required when encryption is enabled")


@dataclass
class BackupManifest:
    """Manifest describing a completed backup."""

    backup_id: str
    backup_type: BackupType
    source_path: str
    destination: str
    created_at: float
    size_bytes: int = 0
    file_count: int = 0
    checksum: str = ""
    encrypted: bool = False
    parent_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "backup_type": self.backup_type.value,
            "source_path": self.source_path,
            "destination": self.destination,
            "created_at": self.created_at,
            "size_bytes": self.size_bytes,
            "file_count": self.file_count,
            "checksum": self.checksum,
            "encrypted": self.encrypted,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupManifest:
        return cls(
            backup_id=data["backup_id"],
            backup_type=BackupType(data["backup_type"]),
            source_path=data["source_path"],
            destination=data["destination"],
            created_at=data["created_at"],
            size_bytes=data.get("size_bytes", 0),
            file_count=data.get("file_count", 0),
            checksum=data.get("checksum", ""),
            encrypted=data.get("encrypted", False),
            parent_id=data.get("parent_id", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class BackupResult:
    """Result of a backup operation."""

    backup_id: str
    status: BackupStatus
    manifest: BackupManifest | None = None
    error: str = ""
    duration_seconds: float = 0.0


class BackupManager:
    """Manages automated backups with incremental, versioned,
    encrypted, multi-destination support and retention policies."""

    def __init__(
        self,
        base_dir: str = ".lidco/backups",
        retention: RetentionPolicy | None = None,
        encryption: EncryptionConfig | None = None,
    ) -> None:
        self._base_dir = Path(base_dir)
        self._retention = retention or RetentionPolicy()
        self._encryption = encryption or EncryptionConfig()
        self._destinations: list[BackupDestination] = []
        self._manifests: list[BackupManifest] = []
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    @property
    def retention(self) -> RetentionPolicy:
        return self._retention

    @property
    def encryption(self) -> EncryptionConfig:
        return self._encryption

    @property
    def manifests(self) -> list[BackupManifest]:
        return list(self._manifests)

    def add_destination(self, destination: BackupDestination) -> None:
        """Register a backup destination."""
        self._destinations.append(destination)

    @property
    def destinations(self) -> list[BackupDestination]:
        return list(self._destinations)

    def create_backup(
        self,
        source_path: str,
        backup_type: BackupType = BackupType.FULL,
        parent_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BackupResult:
        """Create a backup of the given source path."""
        backup_id = uuid.uuid4().hex[:12]
        start = time.time()

        src = Path(source_path)
        if not src.exists():
            return BackupResult(
                backup_id=backup_id,
                status=BackupStatus.FAILED,
                error=f"Source path does not exist: {source_path}",
                duration_seconds=time.time() - start,
            )

        if backup_type == BackupType.INCREMENTAL and not parent_id:
            if self._manifests:
                parent_id = self._manifests[-1].backup_id
            else:
                backup_type = BackupType.FULL

        dest_dir = self._base_dir / backup_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        try:
            files = self._collect_files(src)
            if backup_type == BackupType.INCREMENTAL and parent_id:
                files = self._filter_changed(files, src, parent_id)

            total_size = 0
            file_count = 0
            hasher = hashlib.sha256()

            for rel_path in files:
                full = src / rel_path
                target = dest_dir / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                data = full.read_bytes()

                if self._encryption.enabled:
                    data = self._encrypt(data)

                target.write_bytes(data)
                total_size += len(data)
                file_count += 1
                hasher.update(data)

            manifest = BackupManifest(
                backup_id=backup_id,
                backup_type=backup_type,
                source_path=source_path,
                destination=str(dest_dir),
                created_at=time.time(),
                size_bytes=total_size,
                file_count=file_count,
                checksum=hasher.hexdigest(),
                encrypted=self._encryption.enabled,
                parent_id=parent_id,
                metadata=metadata or {},
            )

            manifest_path = dest_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2))

            self._manifests.append(manifest)

            for dest in self._destinations:
                self._copy_to_destination(dest_dir, dest)

            return BackupResult(
                backup_id=backup_id,
                status=BackupStatus.COMPLETED,
                manifest=manifest,
                duration_seconds=time.time() - start,
            )
        except Exception as exc:
            return BackupResult(
                backup_id=backup_id,
                status=BackupStatus.FAILED,
                error=str(exc),
                duration_seconds=time.time() - start,
            )

    def restore(self, backup_id: str, target_path: str) -> bool:
        """Restore a backup to the target path."""
        manifest = self.get_manifest(backup_id)
        if manifest is None:
            return False

        src_dir = Path(manifest.destination)
        if not src_dir.exists():
            return False

        target = Path(target_path)
        target.mkdir(parents=True, exist_ok=True)

        for item in src_dir.rglob("*"):
            if item.is_file() and item.name != "manifest.json":
                rel = item.relative_to(src_dir)
                dest = target / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                data = item.read_bytes()
                if manifest.encrypted:
                    data = self._decrypt(data)
                dest.write_bytes(data)

        return True

    def get_manifest(self, backup_id: str) -> BackupManifest | None:
        """Look up a manifest by backup ID."""
        for m in self._manifests:
            if m.backup_id == backup_id:
                return m
        return None

    def apply_retention(self) -> list[str]:
        """Apply retention policy, removing old backups. Returns removed IDs."""
        removed: list[str] = []
        cutoff = time.time() - (self._retention.max_age_days * 86400)

        while len(self._manifests) > self._retention.max_versions:
            if len(self._manifests) <= self._retention.min_versions:
                break
            old = self._manifests.pop(0)
            self._remove_backup_files(old)
            removed.append(old.backup_id)

        expired = [
            m for m in self._manifests if m.created_at < cutoff
        ]
        for m in expired:
            if len(self._manifests) <= self._retention.min_versions:
                break
            self._manifests.remove(m)
            self._remove_backup_files(m)
            removed.append(m.backup_id)

        return removed

    def list_backups(self) -> list[BackupManifest]:
        """List all known backups."""
        return list(self._manifests)

    def _collect_files(self, src: Path) -> list[str]:
        """Collect relative file paths from source."""
        if src.is_file():
            return [src.name]
        result: list[str] = []
        for item in sorted(src.rglob("*")):
            if item.is_file():
                result.append(str(item.relative_to(src)))
        return result

    def _filter_changed(
        self, files: list[str], src: Path, parent_id: str
    ) -> list[str]:
        """Filter to only files changed since parent backup."""
        parent = self.get_manifest(parent_id)
        if parent is None:
            return files

        parent_dir = Path(parent.destination)
        changed: list[str] = []
        for rel in files:
            new_file = src / rel
            old_file = parent_dir / rel
            if not old_file.exists():
                changed.append(rel)
            elif new_file.read_bytes() != old_file.read_bytes():
                changed.append(rel)
        return changed

    def _encrypt(self, data: bytes) -> bytes:
        """Simple XOR obfuscation (placeholder for real encryption)."""
        key = self._encryption.key_id.encode() or b"\x42"
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

    def _decrypt(self, data: bytes) -> bytes:
        """Decrypt is same as encrypt for XOR."""
        return self._encrypt(data)

    def _copy_to_destination(
        self, src_dir: Path, dest: BackupDestination
    ) -> None:
        """Copy backup to an additional destination (local only for now)."""
        if dest.destination_type == DestinationType.LOCAL:
            target = Path(dest.path)
            target.mkdir(parents=True, exist_ok=True)
            for item in src_dir.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(src_dir)
                    out = target / src_dir.name / rel
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(item), str(out))

    def _remove_backup_files(self, manifest: BackupManifest) -> None:
        """Remove backup files from disk."""
        dest = Path(manifest.destination)
        if dest.exists():
            shutil.rmtree(str(dest), ignore_errors=True)
