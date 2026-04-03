"""Response cache — exact and similarity-based lookup."""
from __future__ import annotations

import hashlib
from collections import OrderedDict


def _hash_key(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()


def _word_set(text: str) -> set[str]:
    return set(text.lower().split())


def _word_overlap(a: str, b: str) -> float:
    """Jaccard similarity on word sets."""
    sa, sb = _word_set(a), _word_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class ResponseCache:
    """In-memory response cache with exact and similarity lookups."""

    def __init__(self, max_size: int = 1024) -> None:
        self._store: OrderedDict[str, tuple[str, str]] = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def put(self, prompt: str, response: str) -> None:
        """Store a prompt/response pair."""
        key = _hash_key(prompt)
        if key in self._store:
            self._store.move_to_end(key)
            self._store[key] = (prompt, response)
            return
        if len(self._store) >= self._max_size:
            self._store.popitem(last=False)
        self._store[key] = (prompt, response)

    def get(self, prompt: str) -> str | None:
        """Exact-match lookup."""
        key = _hash_key(prompt)
        entry = self._store.get(key)
        if entry is not None:
            self._hits += 1
            self._store.move_to_end(key)
            return entry[1]
        self._misses += 1
        return None

    def get_similar(
        self,
        prompt: str,
        threshold: float = 0.8,
    ) -> str | None:
        """Return the best matching cached response if similarity >= *threshold*."""
        best_score = 0.0
        best_response: str | None = None
        for _key, (cached_prompt, cached_response) in self._store.items():
            score = _word_overlap(prompt, cached_prompt)
            if score >= threshold and score > best_score:
                best_score = score
                best_response = cached_response
        if best_response is not None:
            self._hits += 1
        else:
            self._misses += 1
        return best_response

    def invalidate(self, prompt: str) -> bool:
        """Remove a specific entry. Returns *True* if it existed."""
        key = _hash_key(prompt)
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """Remove all entries and reset stats."""
        self._store.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._store),
        }
