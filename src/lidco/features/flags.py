"""FeatureFlags — percentage-based rollout with environment/user targeting (stdlib only)."""
from __future__ import annotations

import functools
import hashlib
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_UNSET = object()


@dataclass
class FlagConfig:
    name: str
    enabled: bool = False
    rollout: float = 0.0          # 0.0–100.0 percent
    allowlist: list[str] = field(default_factory=list)   # always-on identifiers
    denylist: list[str] = field(default_factory=list)    # always-off identifiers
    metadata: dict[str, Any] = field(default_factory=dict)


class FeatureFlagNotFoundError(KeyError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Feature flag {name!r} not found")
        self.flag_name = name


class FeatureFlags:
    """
    Feature flag manager with percentage-based rollout.

    Parameters
    ----------
    path:
        JSON file for persistence.  Pass ``None`` for in-memory only.
    """

    def __init__(self, path: str | Path | None = "DEFAULT") -> None:
        if path == "DEFAULT":
            path = Path(".lidco") / "feature_flags.json"
        self._path: Path | None = Path(path) if path is not None else None
        self._flags: dict[str, FlagConfig] = {}
        self._lock = threading.Lock()
        if self._path and self._path.exists():
            self._load()

    # ------------------------------------------------------------------ flags

    def define(
        self,
        name: str,
        *,
        enabled: bool = False,
        rollout: float = 0.0,
        allowlist: list[str] | None = None,
        denylist: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FlagConfig:
        """Define or update a feature flag."""
        with self._lock:
            cfg = FlagConfig(
                name=name,
                enabled=enabled,
                rollout=max(0.0, min(100.0, rollout)),
                allowlist=list(allowlist or []),
                denylist=list(denylist or []),
                metadata=dict(metadata or {}),
            )
            self._flags = {**self._flags, name: cfg}
        self._save()
        return cfg

    def remove(self, name: str) -> bool:
        """Remove a flag.  Return True if it existed."""
        with self._lock:
            if name not in self._flags:
                return False
            self._flags = {k: v for k, v in self._flags.items() if k != name}
        self._save()
        return True

    def get_config(self, name: str) -> FlagConfig:
        """Return FlagConfig.  Raises FeatureFlagNotFoundError if missing."""
        with self._lock:
            if name not in self._flags:
                raise FeatureFlagNotFoundError(name)
            return self._flags[name]

    def list_flags(self) -> list[str]:
        with self._lock:
            return sorted(self._flags.keys())

    # ----------------------------------------------------------------- eval

    def is_enabled(self, name: str, identifier: str = "") -> bool:
        """
        Evaluate flag for *identifier*.

        Rules (checked in order):
        1. Flag not found → False
        2. Flag disabled → False
        3. Identifier in denylist → False
        4. Identifier in allowlist → True
        5. Rollout ≥ 100.0 → True
        6. Rollout == 0.0 → False
        7. Hash(flag+identifier) % 100 < rollout → True
        """
        with self._lock:
            cfg = self._flags.get(name)
        if cfg is None:
            return False
        if not cfg.enabled:
            return False
        if identifier in cfg.denylist:
            return False
        if identifier in cfg.allowlist:
            return True
        if cfg.rollout >= 100.0:
            return True
        if cfg.rollout <= 0.0:
            return False
        bucket = self._hash_bucket(name, identifier)
        return bucket < cfg.rollout

    @staticmethod
    def _hash_bucket(flag_name: str, identifier: str) -> float:
        """Return a deterministic float 0.0–100.0 from flag+identifier."""
        key = f"{flag_name}:{identifier}"
        digest = hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()
        return (int(digest[:8], 16) % 10000) / 100.0

    # --------------------------------------------------------------- decorator

    def feature_flag(
        self,
        name: str,
        identifier: str = "",
        default: Any = None,
    ) -> Callable[[F], F]:
        """
        Decorator.  If flag is disabled for *identifier*, return *default*
        instead of calling the function.
        """
        def decorator(fn: F) -> F:
            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                if not self.is_enabled(name, identifier):
                    return default
                return fn(*args, **kwargs)
            return wrapper  # type: ignore[return-value]
        return decorator

    # ------------------------------------------------------------------ persist

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                data = {
                    n: {
                        "enabled": c.enabled,
                        "rollout": c.rollout,
                        "allowlist": c.allowlist,
                        "denylist": c.denylist,
                        "metadata": c.metadata,
                    }
                    for n, c in self._flags.items()
                }
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            flags = {}
            for name, cfg in raw.items():
                flags[name] = FlagConfig(
                    name=name,
                    enabled=cfg.get("enabled", False),
                    rollout=cfg.get("rollout", 0.0),
                    allowlist=cfg.get("allowlist", []),
                    denylist=cfg.get("denylist", []),
                    metadata=cfg.get("metadata", {}),
                )
            with self._lock:
                self._flags = flags
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    def reload(self) -> None:
        """Re-read flags from disk."""
        self._load()

    def __len__(self) -> int:
        with self._lock:
            return len(self._flags)

    def __contains__(self, name: object) -> bool:
        with self._lock:
            return name in self._flags
