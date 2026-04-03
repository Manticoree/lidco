"""KeyRotator — Multiple API keys per provider with rotation strategies."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ApiKey:
    key: str
    provider: str
    usage_count: int = 0
    exhausted: bool = False
    last_used: float = 0.0


class KeyRotator:
    """Rotate API keys per provider using round-robin or least-used strategy."""

    def __init__(self, strategy: str = "round-robin") -> None:
        if strategy not in ("round-robin", "least-used"):
            raise ValueError(f"Unknown strategy: {strategy}")
        self._strategy = strategy
        self._keys: dict[str, list[ApiKey]] = {}
        self._rr_index: dict[str, int] = {}

    def add_key(self, provider: str, key: str) -> ApiKey:
        """Add a key for a provider."""
        api_key = ApiKey(key=key, provider=provider)
        self._keys.setdefault(provider, []).append(api_key)
        self._rr_index.setdefault(provider, 0)
        return api_key

    def remove_key(self, provider: str, key: str) -> bool:
        """Remove a key. Returns True if it existed."""
        keys = self._keys.get(provider, [])
        for i, ak in enumerate(keys):
            if ak.key == key:
                keys.pop(i)
                return True
        return False

    def next_key(self, provider: str) -> ApiKey | None:
        """Get next key using strategy, skipping exhausted keys."""
        keys = self._keys.get(provider, [])
        available = [k for k in keys if not k.exhausted]
        if not available:
            return None
        if self._strategy == "round-robin":
            return self._round_robin(provider, available)
        return self._least_used(available)

    def _round_robin(self, provider: str, available: list[ApiKey]) -> ApiKey:
        idx = self._rr_index.get(provider, 0) % len(available)
        self._rr_index[provider] = idx + 1
        return available[idx]

    def _least_used(self, available: list[ApiKey]) -> ApiKey:
        return min(available, key=lambda k: k.usage_count)

    def mark_exhausted(self, provider: str, key: str) -> bool:
        """Mark a key as exhausted. Returns True if found."""
        for ak in self._keys.get(provider, []):
            if ak.key == key:
                ak.exhausted = True
                return True
        return False

    def mark_used(self, provider: str, key: str) -> ApiKey | None:
        """Increment usage count and update last_used timestamp."""
        for ak in self._keys.get(provider, []):
            if ak.key == key:
                ak.usage_count += 1
                ak.last_used = time.time()
                return ak
        return None

    def reset(self, provider: str) -> int:
        """Reset all keys for provider. Returns count of keys reset."""
        keys = self._keys.get(provider, [])
        for ak in keys:
            ak.exhausted = False
            ak.usage_count = 0
            ak.last_used = 0.0
        self._rr_index[provider] = 0
        return len(keys)

    def keys(self, provider: str) -> list[ApiKey]:
        """Return all keys for a provider."""
        return list(self._keys.get(provider, []))

    def providers(self) -> list[str]:
        """Return all providers."""
        return list(self._keys.keys())

    def summary(self) -> dict:
        """Summary of key state."""
        result: dict = {}
        for provider, keys in self._keys.items():
            active = sum(1 for k in keys if not k.exhausted)
            result[provider] = {
                "total": len(keys),
                "active": active,
                "exhausted": len(keys) - active,
            }
        return result
