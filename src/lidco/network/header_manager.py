"""Case-insensitive HTTP header management."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Header:
    """A single HTTP header."""

    name: str
    value: str


class HeaderManager:
    """Manage HTTP headers with case-insensitive key access."""

    def __init__(self) -> None:
        # _store maps lowercase name -> (original_name, value)
        self._store: dict[str, tuple[str, str]] = {}

    # --- core operations ---

    def set(self, name: str, value: str) -> None:
        """Set a header (overwrites existing, case-insensitive)."""
        self._store[name.lower()] = (name, value)

    def get(self, name: str) -> Optional[str]:
        """Get a header value by name (case-insensitive)."""
        entry = self._store.get(name.lower())
        return entry[1] if entry else None

    def remove(self, name: str) -> bool:
        """Remove a header. Returns ``True`` if it existed."""
        return self._store.pop(name.lower(), None) is not None

    def has(self, name: str) -> bool:
        """Check whether a header is present."""
        return name.lower() in self._store

    def to_dict(self) -> dict[str, str]:
        """Export headers as ``{original_name: value}``."""
        return {orig: val for orig, val in self._store.values()}

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> "HeaderManager":
        """Create a ``HeaderManager`` from a plain dict."""
        mgr = cls()
        for k, v in d.items():
            mgr.set(k, v)
        return mgr

    def merge(self, other: "HeaderManager") -> None:
        """Merge *other*'s headers into this manager (other wins on conflict)."""
        for _key, (orig, val) in other._store.items():
            self.set(orig, val)

    # --- convenience setters ---

    def set_content_type(self, content_type: str = "application/json") -> None:
        """Set the Content-Type header."""
        self.set("Content-Type", content_type)

    def set_authorization(self, value: str) -> None:
        """Set the Authorization header."""
        self.set("Authorization", value)

    def set_accept(self, value: str = "application/json") -> None:
        """Set the Accept header."""
        self.set("Accept", value)

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return f"HeaderManager({self.to_dict()!r})"
