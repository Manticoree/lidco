"""
Memory leak scanner — Q339.

Scans Python source code for reference-cycle patterns, checks for missing
weakref usage, and interrogates the garbage collector.
"""
from __future__ import annotations

import gc
import re


class LeakScanner:
    """Scan source code and runtime state for potential memory leaks."""

    def __init__(self, threshold_mb: float = 50.0) -> None:
        self.threshold_mb = threshold_mb

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_references(self, source_code: str) -> list[dict]:
        """Find potential reference-cycle patterns in *source_code*.

        Returns dicts with "line", "description", "risk".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # self-referential list / dict append inside __init__ or similar.
            if re.search(r"self\.\w+\.append\(self\)", stripped):
                results.append(
                    {
                        "line": lineno,
                        "description": (
                            "Object appends itself to its own collection — "
                            "creates a reference cycle that the GC must collect."
                        ),
                        "risk": "HIGH",
                    }
                )

            # Parent → child → parent circular reference pattern.
            if re.search(r"self\.parent\s*=", stripped) or re.search(
                r"\.parent\s*=\s*self\b", stripped
            ):
                results.append(
                    {
                        "line": lineno,
                        "description": (
                            "Back-reference to parent detected — child stores "
                            "a strong reference to parent, creating a cycle."
                        ),
                        "risk": "HIGH",
                    }
                )

            # Callback / closure capturing self.
            if re.search(r"lambda.*\bself\b", stripped):
                results.append(
                    {
                        "line": lineno,
                        "description": (
                            "Lambda closes over 'self' — if stored on the "
                            "instance this creates a reference cycle."
                        ),
                        "risk": "MEDIUM",
                    }
                )

            # Event handler registration without removal.
            if re.search(r"\.connect\(self\.|\.bind\(self\.|\.add_listener\(self\.", stripped):
                results.append(
                    {
                        "line": lineno,
                        "description": (
                            "Event/signal connected to self — without "
                            "disconnect() in __del__ or close() this keeps the "
                            "object alive as long as the emitter lives."
                        ),
                        "risk": "MEDIUM",
                    }
                )

            # Large data stored on class-level (class var) — shared across instances.
            if re.search(r"^\s*\w+\s*:\s*(?:list|dict|set)\s*=\s*(?:\[|\{)", line):
                results.append(
                    {
                        "line": lineno,
                        "description": (
                            "Mutable class-level attribute — all instances share "
                            "the same object, which may grow without bound."
                        ),
                        "risk": "LOW",
                    }
                )

            # Unbounded cache / registry growth.
            if re.search(r"_cache\s*=\s*\{\}", stripped) or re.search(
                r"_registry\s*=\s*\{\}", stripped
            ):
                results.append(
                    {
                        "line": lineno,
                        "description": (
                            "Unbounded dict used as cache/registry — "
                            "will grow indefinitely without eviction."
                        ),
                        "risk": "MEDIUM",
                    }
                )

        return results

    def audit_weak_refs(self, source_code: str) -> list[dict]:
        """Check where weakref should be used but is not.

        Returns dicts with "line", "pattern", "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()
        uses_weakref = "weakref" in source_code

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Callback list stored without weakref.
            if re.search(r"self\._(?:callbacks|listeners|handlers|observers)\s*=\s*\[\]", stripped):
                if not uses_weakref:
                    results.append(
                        {
                            "line": lineno,
                            "pattern": stripped,
                            "suggestion": (
                                "Store callbacks as weakref.ref() or use "
                                "weakref.WeakSet() / weakref.WeakValueDictionary() "
                                "to avoid keeping subscribers alive."
                            ),
                        }
                    )

            # Strong parent reference.
            if re.search(r"self\.parent\s*=\s*\w+", stripped):
                if not uses_weakref:
                    results.append(
                        {
                            "line": lineno,
                            "pattern": stripped,
                            "suggestion": (
                                "Replace 'self.parent = parent' with "
                                "'self.parent = weakref.ref(parent)' to break "
                                "the parent-child reference cycle."
                            ),
                        }
                    )

            # Cache dict without LRU or weakref.
            if re.search(r"self\._cache\s*=\s*\{\}", stripped):
                if not uses_weakref and "lru_cache" not in source_code and "LRUCache" not in source_code:
                    results.append(
                        {
                            "line": lineno,
                            "pattern": stripped,
                            "suggestion": (
                                "Use weakref.WeakValueDictionary() for caches "
                                "keyed by mutable objects, or use "
                                "functools.lru_cache / a bounded LRUCache."
                            ),
                        }
                    )

        return results

    def get_gc_stats(self) -> dict:
        """Return current garbage-collector statistics."""
        counts = gc.get_count()          # (gen0, gen1, gen2)
        thresholds = gc.get_threshold()  # (thresh0, thresh1, thresh2)
        stats = gc.get_stats()           # list of per-generation dicts

        total_collections = sum(s.get("collections", 0) for s in stats)
        total_collected = sum(s.get("collected", 0) for s in stats)
        total_uncollectable = sum(s.get("uncollectable", 0) for s in stats)

        return {
            "collections": total_collections,
            "collected": total_collected,
            "uncollectable": total_uncollectable,
            "threshold": list(thresholds),
            "counts": list(counts),
        }

    def check_threshold(self, current_mb: float) -> dict:
        """Check whether *current_mb* exceeds the configured threshold.

        Returns "exceeded", "current_mb", "threshold_mb", "message".
        """
        exceeded = current_mb > self.threshold_mb
        if exceeded:
            message = (
                f"Memory usage {current_mb:.1f} MB exceeds threshold "
                f"{self.threshold_mb:.1f} MB — potential memory leak detected."
            )
        else:
            message = (
                f"Memory usage {current_mb:.1f} MB is within threshold "
                f"{self.threshold_mb:.1f} MB."
            )
        return {
            "exceeded": exceeded,
            "current_mb": current_mb,
            "threshold_mb": self.threshold_mb,
            "message": message,
        }
