"""Import serialized sessions and merge with current state."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json


class ImportStatus(str, Enum):
    """Outcome of an import operation."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class ImportResult:
    """Immutable result of an import operation."""

    status: ImportStatus
    messages_imported: int = 0
    files_resolved: int = 0
    conflicts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


_REQUIRED_FIELDS = ("session_id", "version", "messages")


class SessionImporter:
    """Validate, import, and merge serialized session snapshots."""

    def __init__(self) -> None:
        self._supported_versions = ("1.0",)

    def validate_schema(self, snapshot_data: dict) -> list[str]:
        """Return a list of validation errors (empty means valid)."""
        errors: list[str] = []
        for f in _REQUIRED_FIELDS:
            if f not in snapshot_data:
                errors.append(f"Missing required field: {f}")
        version = snapshot_data.get("version", "")
        if version and version not in self._supported_versions:
            errors.append(f"Unsupported schema version: {version}")
        msgs = snapshot_data.get("messages")
        if msgs is not None and not isinstance(msgs, list):
            errors.append("Field 'messages' must be a list")
        return errors

    def import_snapshot(self, snapshot_data: dict) -> ImportResult:
        """Import a snapshot dict, returning an ImportResult."""
        errors = self.validate_schema(snapshot_data)
        if errors:
            return ImportResult(
                status=ImportStatus.FAILED,
                warnings=tuple(errors),
            )
        messages = snapshot_data.get("messages", [])
        files = snapshot_data.get("files", [])
        local_files: list[str] = []
        resolved, conflicts = self.resolve_conflicts(local_files, files)
        status = ImportStatus.SUCCESS if not conflicts else ImportStatus.CONFLICT
        return ImportResult(
            status=status,
            messages_imported=len(messages),
            files_resolved=len(resolved),
            conflicts=tuple(conflicts),
        )

    def resolve_conflicts(
        self, local_files: list[str], remote_files: list[str],
    ) -> tuple[list[str], list[str]]:
        """Resolve file conflicts between local and remote.

        Returns (resolved, conflicts) where conflicts are files in both sets.
        """
        local_set = set(local_files)
        resolved: list[str] = []
        conflicts: list[str] = []
        for f in remote_files:
            if f in local_set:
                conflicts.append(f)
            else:
                resolved.append(f)
        return resolved, conflicts

    def merge_messages(
        self, local: list[dict], remote: list[dict],
    ) -> list[dict]:
        """Append remote messages after local, deduplicating by content hash."""
        seen: set[str] = set()
        result: list[dict] = []
        for msg in local:
            h = hashlib.sha256(json.dumps(msg, sort_keys=True).encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                result.append(msg)
        for msg in remote:
            h = hashlib.sha256(json.dumps(msg, sort_keys=True).encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                result.append(msg)
        return result

    def summary(self, result: ImportResult) -> str:
        """Human-readable summary of an import result."""
        parts = [f"Status: {result.status.value}"]
        parts.append(f"Messages imported: {result.messages_imported}")
        parts.append(f"Files resolved: {result.files_resolved}")
        if result.conflicts:
            parts.append(f"Conflicts: {', '.join(result.conflicts)}")
        if result.warnings:
            parts.append(f"Warnings: {'; '.join(result.warnings)}")
        return " | ".join(parts)
