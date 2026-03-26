"""KeyValueStore — persistent TTL key-value store (stdlib only)."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

_DEFAULT_PATH = Path(".lidco") / "kv_store.json"


@dataclass
class KVEntry:
    key: str
    value: object
    ttl: float | None = None
    created_at: float = 0.0
    expires_at: float | None = None

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class NamespacedKVStore:
    """Proxy that prefixes all keys with ``{prefix}:``."""

    def __init__(self, store: "KVStore", prefix: str) -> None:
        self._store = store
        self._prefix = prefix

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    def set(self, key: str, value: object, ttl: float | None = None) -> None:
        self._store.set(self._full_key(key), value, ttl=ttl)

    def get(self, key: str, default: object = None) -> object:
        return self._store.get(self._full_key(key), default)

    def delete(self, key: str) -> bool:
        return self._store.delete(self._full_key(key))

    def list(self, prefix: str | None = None) -> list[str]:
        ns_prefix = f"{self._prefix}:"
        full_prefix = f"{ns_prefix}{prefix}" if prefix else ns_prefix
        full_keys = self._store.list(full_prefix)
        return [k[len(ns_prefix):] for k in full_keys]


class KVStore:
    """
    Persistent key-value store with TTL and namespaces.

    Parameters
    ----------
    path:
        JSON file for persistence.  *None* → in-memory only (no disk I/O).
        Defaults to ``.lidco/kv_store.json`` when omitted entirely.
    """

    def __init__(self, path: object = "DEFAULT") -> None:
        if path == "DEFAULT":
            self._path: Path | None = _DEFAULT_PATH
        elif path is None:
            self._path = None
        else:
            self._path = Path(str(path))

        self._data: dict[str, KVEntry] = {}
        self._lock = threading.Lock()
        if self._path is not None:
            self._load()

    # ----------------------------------------------------------------- private

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            with self._lock:
                self._data = {}
                for k, v in raw.items():
                    entry = KVEntry(
                        key=v["key"],
                        value=v["value"],
                        ttl=v.get("ttl"),
                        created_at=v.get("created_at", time.time()),
                        expires_at=v.get("expires_at"),
                    )
                    self._data[k] = entry
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    def save(self) -> None:
        """Persist to JSON file."""
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            serializable = {
                k: {
                    "key": e.key,
                    "value": e.value,
                    "ttl": e.ttl,
                    "created_at": e.created_at,
                    "expires_at": e.expires_at,
                }
                for k, e in self._data.items()
            }
        self._path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

    def _auto_save(self) -> None:
        if self._path is not None:
            self.save()

    # ------------------------------------------------------------------ public

    def set(self, key: str, value: object, ttl: float | None = None) -> None:
        expires_at = (time.time() + ttl) if ttl is not None else None
        entry = KVEntry(key=key, value=value, ttl=ttl, expires_at=expires_at)
        with self._lock:
            self._data = {**self._data, key: entry}
        self._auto_save()

    def get(self, key: str, default: object = None) -> object:
        with self._lock:
            entry = self._data.get(key)
        if entry is None:
            return default
        if entry.is_expired():
            with self._lock:
                self._data = {k: v for k, v in self._data.items() if k != key}
            return default
        return entry.value

    def delete(self, key: str) -> bool:
        with self._lock:
            if key not in self._data:
                return False
            self._data = {k: v for k, v in self._data.items() if k != key}
        self._auto_save()
        return True

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def list(self, prefix: str | None = None) -> list[str]:
        """Return all non-expired keys, optionally filtered by prefix."""
        with self._lock:
            keys = [(k, e) for k, e in self._data.items()]
        result = [k for k, e in keys if not e.is_expired()]
        if prefix:
            result = [k for k in result if k.startswith(prefix)]
        return sorted(result)

    def flush_expired(self) -> int:
        """Remove all expired entries.  Return count removed."""
        with self._lock:
            expired = [k for k, e in self._data.items() if e.is_expired()]
            self._data = {k: v for k, v in self._data.items() if k not in expired}
        if expired:
            self._auto_save()
        return len(expired)

    def ns(self, prefix: str) -> NamespacedKVStore:
        """Return a namespaced proxy."""
        return NamespacedKVStore(self, prefix)

    def clear(self) -> int:
        """Remove all entries.  Return count."""
        with self._lock:
            count = len(self._data)
            self._data = {}
        self._auto_save()
        return count

    def count(self) -> int:
        """Number of non-expired entries."""
        return len(self.list())
