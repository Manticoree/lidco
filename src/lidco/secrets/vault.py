"""VaultClient — abstract vault with in-memory backend and lease management."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class VaultSecret:
    """A versioned secret stored in the vault."""

    key: str
    value: str
    version: int = 1
    created_at: float = 0.0
    expires_at: float | None = None
    metadata: dict = field(default_factory=dict)


class VaultClient:
    """In-memory vault with versioning and TTL/lease support."""

    def __init__(self, backend: str = "memory") -> None:
        self._backend = backend
        # key -> list of VaultSecret (versions, newest last)
        self._store: dict[str, list[VaultSecret]] = {}

    def put(
        self,
        key: str,
        value: str,
        ttl: float | None = None,
        metadata: dict | None = None,
    ) -> VaultSecret:
        """Store a secret, creating a new version if it already exists."""
        now = time.time()
        versions = self._store.get(key, [])
        version = len(versions) + 1
        secret = VaultSecret(
            key=key,
            value=value,
            version=version,
            created_at=now,
            expires_at=now + ttl if ttl is not None else None,
            metadata=metadata if metadata is not None else {},
        )
        if key not in self._store:
            self._store[key] = []
        self._store[key].append(secret)
        return secret

    def get(self, key: str, version: int | None = None) -> VaultSecret | None:
        """Retrieve a secret.  Returns None if not found or expired."""
        versions = self._store.get(key)
        if not versions:
            return None
        if version is not None:
            for v in versions:
                if v.version == version:
                    if v.expires_at is not None and v.expires_at <= time.time():
                        return None
                    return v
            return None
        # Latest version
        latest = versions[-1]
        if latest.expires_at is not None and latest.expires_at <= time.time():
            return None
        return latest

    def delete(self, key: str) -> bool:
        """Remove all versions of a secret.  Returns True if it existed."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def list_keys(self, prefix: str = "") -> list[str]:
        """Return keys matching the given prefix (non-expired latest version)."""
        now = time.time()
        result: list[str] = []
        for key, versions in self._store.items():
            if not key.startswith(prefix):
                continue
            latest = versions[-1]
            if latest.expires_at is not None and latest.expires_at <= now:
                continue
            result.append(key)
        return sorted(result)

    def versions(self, key: str) -> list[VaultSecret]:
        """Return all versions of a secret."""
        return list(self._store.get(key, []))

    def renew_lease(self, key: str, ttl: float) -> VaultSecret | None:
        """Extend the TTL of the latest version.  Returns None if not found."""
        versions = self._store.get(key)
        if not versions:
            return None
        latest = versions[-1]
        latest.expires_at = time.time() + ttl
        return latest

    def expired(self) -> list[VaultSecret]:
        """Return all secrets whose latest version has expired."""
        now = time.time()
        result: list[VaultSecret] = []
        for versions in self._store.values():
            if not versions:
                continue
            latest = versions[-1]
            if latest.expires_at is not None and latest.expires_at <= now:
                result.append(latest)
        return result

    def summary(self) -> dict:
        """Return vault statistics."""
        total_versions = sum(len(v) for v in self._store.values())
        now = time.time()
        expired_count = sum(
            1 for versions in self._store.values()
            if versions and versions[-1].expires_at is not None and versions[-1].expires_at <= now
        )
        return {
            "backend": self._backend,
            "keys": len(self._store),
            "total_versions": total_versions,
            "expired": expired_count,
        }
