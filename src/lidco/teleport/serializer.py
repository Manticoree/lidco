"""Serialize session state to portable format."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import time
import zlib


@dataclass(frozen=True)
class SessionSnapshot:
    """Immutable snapshot of a session state."""

    session_id: str
    version: str = "1.0"
    timestamp: float = field(default_factory=time.time)
    messages: tuple[dict, ...] = ()
    files: tuple[str, ...] = ()
    config: tuple[tuple[str, str], ...] = ()
    checksum: str = ""


def _compute_checksum(
    session_id: str,
    messages: tuple[dict, ...],
    files: tuple[str, ...],
    config: tuple[tuple[str, str], ...],
) -> str:
    """Compute SHA-256 checksum from session content."""
    h = hashlib.sha256()
    h.update(session_id.encode())
    h.update(json.dumps(list(messages), sort_keys=True).encode())
    h.update(json.dumps(list(files)).encode())
    h.update(json.dumps(list(config)).encode())
    return h.hexdigest()


class SessionSerializer:
    """Serialize / deserialize session snapshots."""

    def __init__(self, schema_version: str = "1.0") -> None:
        self._schema_version = schema_version

    def serialize(
        self,
        session_id: str,
        messages: list[dict],
        files: list[str] | None = None,
        config: dict[str, str] | None = None,
    ) -> SessionSnapshot:
        """Create an immutable snapshot with computed checksum."""
        msgs = tuple(messages)
        fls = tuple(files or [])
        cfg = tuple(sorted((config or {}).items()))
        checksum = _compute_checksum(session_id, msgs, fls, cfg)
        return SessionSnapshot(
            session_id=session_id,
            version=self._schema_version,
            messages=msgs,
            files=fls,
            config=cfg,
            checksum=checksum,
        )

    def to_json(self, snapshot: SessionSnapshot) -> str:
        """Serialize snapshot to JSON string."""
        payload = {
            "session_id": snapshot.session_id,
            "version": snapshot.version,
            "timestamp": snapshot.timestamp,
            "messages": list(snapshot.messages),
            "files": list(snapshot.files),
            "config": [list(pair) for pair in snapshot.config],
            "checksum": snapshot.checksum,
        }
        return json.dumps(payload, sort_keys=True)

    def from_json(self, data: str) -> SessionSnapshot:
        """Deserialize JSON string to snapshot, validating checksum."""
        obj = json.loads(data)
        snap = SessionSnapshot(
            session_id=obj["session_id"],
            version=obj.get("version", "1.0"),
            timestamp=obj.get("timestamp", 0.0),
            messages=tuple(obj.get("messages", [])),
            files=tuple(obj.get("files", [])),
            config=tuple(tuple(p) for p in obj.get("config", [])),
            checksum=obj.get("checksum", ""),
        )
        if snap.checksum and not self.verify_checksum(snap):
            raise ValueError("Checksum mismatch — snapshot may be corrupted")
        return snap

    def compress(self, data: str) -> bytes:
        """Compress a string with zlib."""
        return zlib.compress(data.encode())

    def decompress(self, data: bytes) -> str:
        """Decompress zlib bytes to string."""
        return zlib.decompress(data).decode()

    def verify_checksum(self, snapshot: SessionSnapshot) -> bool:
        """Return True if snapshot checksum matches computed value."""
        expected = _compute_checksum(
            snapshot.session_id, snapshot.messages, snapshot.files, snapshot.config,
        )
        return snapshot.checksum == expected

    def summary(self, snapshot: SessionSnapshot) -> str:
        """Human-readable summary of a snapshot."""
        return (
            f"Session {snapshot.session_id} v{snapshot.version} | "
            f"{len(snapshot.messages)} messages | "
            f"{len(snapshot.files)} files | "
            f"checksum {snapshot.checksum[:12]}..."
        )
