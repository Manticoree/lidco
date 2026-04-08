"""
Config race condition detector — Q339.

Analyzes Python source code for race conditions in configuration access,
lock contention patterns, and potential deadlocks.
"""
from __future__ import annotations

import re


class ConfigRaceDetector:
    """Detect race conditions and synchronisation issues in config access code."""

    def __init__(self) -> None:
        self.findings: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_races(self, source_code: str) -> list[dict]:
        """Analyse *source_code* for race conditions in config / shared-dict access.

        Returns a list of finding dicts, each with keys:
          "line", "type", "description", "severity"
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        # Track whether we are inside a lock context.
        lock_depth = 0

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Track lock context entry / exit.
            # Matches: with lock:  / with self._lock:  / with self._rw_lock:
            if re.search(r"with\s+(?:\w+\.)*\w*[Ll]ock\w*\s*:", stripped):
                lock_depth += 1
            if re.search(r"\.release\(\)", stripped):
                lock_depth = max(0, lock_depth - 1)

            # Unsynchronised dict write (shared config mutation without lock).
            if re.search(r"(?:config|settings|_config|_settings)\s*\[.+\]\s*=", stripped):
                if lock_depth == 0:
                    results.append(
                        {
                            "line": lineno,
                            "type": "unsynchronised_write",
                            "description": (
                                "Config dict written without holding a lock — "
                                "unsafe in multi-threaded context"
                            ),
                            "severity": "HIGH",
                        }
                    )

            # Concurrent dict.update() on shared config.
            if re.search(r"(?:config|settings|_config|_settings)\.update\(", stripped):
                if lock_depth == 0:
                    results.append(
                        {
                            "line": lineno,
                            "type": "unsynchronised_update",
                            "description": (
                                "Config.update() called without a lock — "
                                "may cause torn reads in concurrent code"
                            ),
                            "severity": "HIGH",
                        }
                    )

            # Thread-unsafe global access pattern: `global foo` declaration.
            if re.search(r"^\s*global\s+\w+", line):
                results.append(
                    {
                        "line": lineno,
                        "type": "global_mutation",
                        "description": (
                            "Global variable declared — shared global state is "
                            "a common race condition source in multi-threaded code"
                        ),
                        "severity": "MEDIUM",
                    }
                )

            # setdefault called without lock (check-then-act).
            if re.search(r"\.setdefault\(", stripped) and lock_depth == 0:
                results.append(
                    {
                        "line": lineno,
                        "type": "check_then_act",
                        "description": (
                            "setdefault() is not atomic under threading — "
                            "use a lock to guard the call"
                        ),
                        "severity": "MEDIUM",
                    }
                )

            # __setattr__ / __setitem__ override without thread-safety note.
            if re.search(r"def __setattr__", stripped) or re.search(r"def __setitem__", stripped):
                results.append(
                    {
                        "line": lineno,
                        "type": "custom_setter",
                        "description": (
                            "Custom setter detected — ensure it uses a lock "
                            "if instances are shared across threads"
                        ),
                        "severity": "LOW",
                    }
                )

        self.findings = results
        return results

    def analyze_lock_contention(self, source_code: str) -> list[dict]:
        """Find lock usage patterns and detect potential contention.

        Returns a list of dicts with "lock_name", "contention_risk", "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        lock_usage: dict[str, list[int]] = {}

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Capture lock acquisitions: with self._lock / with lock / lock.acquire()
            for pattern in [
                r"with\s+(self\.\w*[Ll]ock\w*)\b",
                r"with\s+(\w*[Ll]ock\w*)\b",
                r"(self\.\w*[Ll]ock\w*)\.acquire\(",
                r"(\w*[Ll]ock\w*)\.acquire\(",
            ]:
                m = re.search(pattern, stripped)
                if m:
                    name = m.group(1)
                    lock_usage.setdefault(name, []).append(lineno)

        for lock_name, usages in lock_usage.items():
            if len(usages) > 5:
                risk = "HIGH"
                suggestion = (
                    f"Lock '{lock_name}' is acquired on {len(usages)} sites — "
                    "consider finer-grained locking or a read-write lock."
                )
            elif len(usages) > 2:
                risk = "MEDIUM"
                suggestion = (
                    f"Lock '{lock_name}' is shared across {len(usages)} call sites — "
                    "profile under load to detect bottlenecks."
                )
            else:
                risk = "LOW"
                suggestion = (
                    f"Lock '{lock_name}' usage looks contained ({len(usages)} sites)."
                )

            results.append(
                {
                    "lock_name": lock_name,
                    "contention_risk": risk,
                    "suggestion": suggestion,
                }
            )

        return results

    def detect_deadlocks(self, source_code: str) -> list[dict]:
        """Find potential deadlock patterns (nested locks, inconsistent ordering).

        Returns dicts with "locks", "description", "fix".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        # Collect sequences of lock acquisitions per function block.
        current_func: str | None = None
        func_lock_seq: dict[str, list[tuple[int, str]]] = {}

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            func_match = re.match(r"def\s+(\w+)\s*\(", stripped)
            if func_match:
                current_func = func_match.group(1)
                func_lock_seq.setdefault(current_func, [])

            if current_func:
                for pattern in [
                    r"with\s+(self\.\w*[Ll]ock\w*)\b",
                    r"with\s+(\w*[Ll]ock\w*)\b",
                ]:
                    m = re.search(pattern, stripped)
                    if m:
                        func_lock_seq[current_func].append((lineno, m.group(1)))

        # Detect nested lock acquisition within the same function.
        for func, seq in func_lock_seq.items():
            if len(seq) >= 2:
                locks = [name for _, name in seq]
                unique_locks = list(dict.fromkeys(locks))
                if len(unique_locks) >= 2:
                    results.append(
                        {
                            "locks": unique_locks,
                            "description": (
                                f"Function '{func}' acquires multiple locks "
                                f"({', '.join(unique_locks)}) — risk of deadlock "
                                "if another function acquires them in reverse order."
                            ),
                            "fix": (
                                "Establish a canonical global lock-acquisition order "
                                "and apply it consistently across all call sites."
                            ),
                        }
                    )

        # Detect acquire() without paired release() (missed release on error path).
        acquire_count = len(re.findall(r"\.acquire\(", source_code))
        release_count = len(re.findall(r"\.release\(", source_code))
        if acquire_count > release_count:
            results.append(
                {
                    "locks": ["unknown"],
                    "description": (
                        f"acquire() called {acquire_count} times but release() "
                        f"only {release_count} times — possible lock leak on "
                        "exception paths."
                    ),
                    "fix": (
                        "Use 'with lock:' context manager instead of "
                        "manual acquire/release to guarantee release on exceptions."
                    ),
                }
            )

        return results

    def suggest_fixes(self, findings: list[dict]) -> list[str]:
        """Generate actionable fix suggestions from a list of findings."""
        suggestions: list[str] = []
        severity_map: dict[str, str] = {
            "HIGH": "[HIGH] ",
            "MEDIUM": "[MEDIUM] ",
            "LOW": "[LOW] ",
        }

        type_advice: dict[str, str] = {
            "unsynchronised_write": (
                "Wrap config writes with 'with self._lock:' to prevent torn writes."
            ),
            "unsynchronised_update": (
                "Guard config.update() calls with a threading.Lock to avoid race conditions."
            ),
            "global_mutation": (
                "Replace mutable globals with thread-local storage "
                "(threading.local()) or pass state explicitly."
            ),
            "check_then_act": (
                "Replace setdefault() with a lock-guarded "
                "'if key not in d: d[key] = value' pattern."
            ),
            "custom_setter": (
                "Add a threading.Lock to custom __setattr__/__setitem__ "
                "if objects are shared across threads."
            ),
        }

        seen: set[str] = set()
        for finding in findings:
            ftype = finding.get("type", "unknown")
            severity = finding.get("severity", "LOW")
            prefix = severity_map.get(severity, "")
            advice = type_advice.get(ftype, f"Review line {finding.get('line')} manually.")
            msg = f"{prefix}{advice}"
            if msg not in seen:
                seen.add(msg)
                suggestions.append(msg)

        if not suggestions:
            suggestions.append("No issues found — config access looks safe.")

        return suggestions
