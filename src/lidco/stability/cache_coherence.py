"""
Cache Coherence Checker.

Verifies that caches remain consistent with their backing sources,
identifies stale entries, validates invalidation event sequences,
and checks TTL accuracy.
"""
from __future__ import annotations

import time


class CacheCoherenceChecker:
    """Checks cache consistency, staleness, invalidation, and TTL accuracy."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_consistency(self, cache: dict, source: dict) -> dict:
        """Verify cache matches source data.

        Args:
            cache: Current cache dict mapping key -> value.
            source: Authoritative source dict mapping key -> value.

        Returns:
            dict with keys:
                "consistent" (bool): True if cache perfectly matches source
                "stale_keys" (list): keys whose cached value differs from source
                "missing_keys" (list): keys in source but not in cache
                "extra_keys" (list): keys in cache but not in source
        """
        stale_keys: list = []
        missing_keys: list = []
        extra_keys: list = []

        source_set = set(source.keys())
        cache_set = set(cache.keys())

        missing_keys = sorted(source_set - cache_set)
        extra_keys = sorted(cache_set - source_set)

        for key in source_set & cache_set:
            if cache[key] != source[key]:
                stale_keys.append(key)

        stale_keys.sort()

        consistent = not stale_keys and not missing_keys and not extra_keys

        return {
            "consistent": consistent,
            "stale_keys": stale_keys,
            "missing_keys": missing_keys,
            "extra_keys": extra_keys,
        }

    def find_stale_entries(
        self,
        cache: dict,
        timestamps: dict,
        max_age: float = 3600.0,
    ) -> list[dict]:
        """Find cache entries that have exceeded their maximum age.

        Args:
            cache: Cache dict mapping key -> value.
            timestamps: Dict mapping key -> creation/update timestamp (Unix epoch).
            max_age: Maximum allowed age in seconds before an entry is stale.

        Returns:
            List of dicts with "key", "age", "max_age", "stale" (bool).
        """
        now = time.time()
        results: list[dict] = []

        for key in cache:
            ts = timestamps.get(key)
            if ts is None:
                # No timestamp info — treat as maximally stale
                age = float("inf")
                stale = True
            else:
                age = now - ts
                stale = age > max_age

            results.append({
                "key": key,
                "age": age,
                "max_age": max_age,
                "stale": stale,
            })

        return results

    def verify_invalidation(self, events: list[dict]) -> dict:
        """Verify that cache invalidation events are logically correct.

        Events are ordered by timestamp and have:
            "type": "set" | "invalidate" | "expire"
            "key": cache key
            "timestamp": Unix epoch float

        Checks performed:
        - "invalidate" after "set" for the same key is valid.
        - "set" after "invalidate"/"expire" is valid (re-population).
        - Duplicate "set" without intervening "invalidate"/"expire" is a
          potential missed-invalidation warning.
        - "invalidate" / "expire" for a key that was never set is a warning.

        Returns:
            dict with keys:
                "correct" (bool): True if no issues found
                "issues" (list[str]): descriptions of detected issues
        """
        issues: list[str] = []

        # Track the current state of each key:  "set" | "invalidated" | None
        key_state: dict[str, str] = {}

        sorted_events = sorted(events, key=lambda e: e.get("timestamp", 0))

        for event in sorted_events:
            etype = event.get("type", "")
            key = event.get("key", "")

            if etype == "set":
                if key_state.get(key) == "set":
                    issues.append(
                        f"Key '{key}' set again without prior invalidation — possible missed invalidation"
                    )
                key_state[key] = "set"

            elif etype in ("invalidate", "expire"):
                if key not in key_state or key_state[key] != "set":
                    issues.append(
                        f"Key '{key}' invalidated/expired but was not in a 'set' state"
                    )
                key_state[key] = "invalidated"

            elif etype:
                issues.append(f"Unknown event type '{etype}' for key '{key}'")

        return {
            "correct": len(issues) == 0,
            "issues": issues,
        }

    def check_ttl_accuracy(self, entries: list[dict]) -> list[dict]:
        """Check TTL accuracy for cache entries.

        Each entry dict has:
            "key": cache key
            "ttl": expected TTL in seconds
            "created_at": Unix epoch when the entry was created
            "expected_expiry": Unix epoch when it should expire

        Checks whether expected_expiry == created_at + ttl within a 1-second
        tolerance.

        Returns:
            List of dicts with "key", "expected_expiry", "drift" (seconds), "accurate" (bool).
        """
        results: list[dict] = []
        tolerance = 1.0  # 1-second drift tolerance

        for entry in entries:
            key = entry.get("key", "")
            ttl = entry.get("ttl", 0)
            created_at = entry.get("created_at", 0)
            expected_expiry = entry.get("expected_expiry", 0)

            computed_expiry = created_at + ttl
            drift = abs(expected_expiry - computed_expiry)
            accurate = drift <= tolerance

            results.append({
                "key": key,
                "expected_expiry": expected_expiry,
                "drift": drift,
                "accurate": accurate,
            })

        return results
