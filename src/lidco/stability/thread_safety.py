"""
Thread Safety Analyzer — Q343.

Finds unguarded shared mutable state, analyzes lock usage patterns,
audits non-atomic operations, and verifies threading.local() usage.
"""
from __future__ import annotations

import re


class ThreadSafetyAnalyzer:
    """Analyze Python source code for thread-safety issues."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_unguarded_state(self, source_code: str) -> list[dict]:
        """Find shared mutable state without lock protection.

        Targets module-level dicts/lists that are modified inside
        functions/methods without an enclosing lock context manager.

        Returns dicts with "line", "variable", "issue", "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        # Collect module-level mutable names (dicts/lists defined at col 0).
        module_level_mutables: set[str] = set()
        for line in lines:
            m = re.match(r'^(\w+)\s*(?::\s*\w[\w\[\],\s]*?)?\s*=\s*(?:\[|\{|list\(|dict\()', line)
            if m:
                module_level_mutables.add(m.group(1))

        # Also pick up class-level attributes that are mutable collections.
        class_level_mutables: set[str] = set()
        for line in lines:
            m = re.match(r'^\s{4}(\w+)\s*(?::\s*\w[\w\[\],\s]*?)?\s*=\s*(?:\[|\{|list\(|dict\()', line)
            if m:
                class_level_mutables.add(m.group(1))

        all_shared = module_level_mutables | class_level_mutables

        def _inside_lock_block(lineno: int, all_lines: list[str]) -> bool:
            """Check whether *lineno* is nested inside a 'with <lock>:' block."""
            current_indent = len(all_lines[lineno - 1]) - len(all_lines[lineno - 1].lstrip())
            for i in range(lineno - 2, max(-1, lineno - 50), -1):
                l = all_lines[i]
                if not l.strip():
                    continue
                indent = len(l) - len(l.lstrip())
                if indent < current_indent:
                    if re.search(r'\bwith\b.*\b(?:lock|Lock|RLock|mutex|Mutex|_lock|acquire)\b', l, re.IGNORECASE):
                        return True
                    # Hit outer scope that is not a lock — stop.
                    if re.search(r'\bdef\b|\bclass\b|\bif\b|\bfor\b|\bwhile\b|\bwith\b', l):
                        break
            return False

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Detect mutations: .append(), .extend(), .update(), .pop(),
            # .clear(), direct index assignment on shared names.
            for name in all_shared:
                # e.g. shared_list.append(...) or shared_dict["key"] = ...
                mutation_re = (
                    rf'\b{re.escape(name)}\s*'
                    rf'(?:\.\s*(?:append|extend|update|pop|clear|insert|remove|setdefault|discard)\s*\()'
                    rf'|{re.escape(name)}\s*\[.*?\]\s*='
                )
                if re.search(mutation_re, stripped):
                    guarded = _inside_lock_block(lineno, lines)
                    if not guarded:
                        results.append(
                            {
                                "line": lineno,
                                "variable": name,
                                "issue": (
                                    f"Shared mutable state '{name}' is mutated "
                                    "without holding a lock."
                                ),
                                "suggestion": (
                                    f"Protect mutations to '{name}' with "
                                    "'with lock:' or use a thread-safe data structure "
                                    "such as queue.Queue."
                                ),
                            }
                        )
                        break  # one finding per line

        return results

    def analyze_locks(self, source_code: str) -> list[dict]:
        """Analyze lock usage patterns (Lock, RLock, Semaphore).

        Returns dicts with "line", "lock_type", "usage", "issues" (list of str).
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        # Track lock variable names and their types.
        lock_vars: dict[str, str] = {}
        for lineno, line in enumerate(lines, start=1):
            m = re.search(
                r'(\w+)\s*=\s*threading\.(Lock|RLock|Semaphore|BoundedSemaphore)\(\)',
                line,
            )
            if m:
                lock_vars[m.group(1)] = m.group(2)

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Detect .acquire() / .release() direct calls (prefer context manager).
            for var, ltype in lock_vars.items():
                if re.search(rf'\b{re.escape(var)}\s*\.\s*acquire\s*\(', stripped):
                    issues: list[str] = []
                    # Check if there is a corresponding .release() in ±20 lines.
                    window = lines[lineno : min(len(lines), lineno + 20)]
                    has_release = any(
                        re.search(rf'\b{re.escape(var)}\s*\.\s*release\s*\(', l)
                        for l in window
                    )
                    if not has_release:
                        issues.append(
                            "acquire() without a visible release() — use 'with lock:' instead"
                        )
                    else:
                        issues.append(
                            "Manual acquire()/release() — prefer 'with lock:' to guarantee release"
                        )
                    results.append(
                        {
                            "line": lineno,
                            "lock_type": ltype,
                            "usage": "manual_acquire",
                            "issues": issues,
                        }
                    )

                elif re.search(rf'with\s+{re.escape(var)}\b', stripped):
                    results.append(
                        {
                            "line": lineno,
                            "lock_type": ltype,
                            "usage": "context_manager",
                            "issues": [],
                        }
                    )

            # Detect anonymous lock creation (not stored in a named variable).
            if re.search(r'with\s+threading\.(Lock|RLock|Semaphore)\(\)', stripped):
                results.append(
                    {
                        "line": lineno,
                        "lock_type": "anonymous",
                        "usage": "anonymous_lock",
                        "issues": [
                            "Lock created inline inside 'with' — a new lock is acquired each time, "
                            "providing no mutual exclusion across calls."
                        ],
                    }
                )

        return results

    def audit_atomic_ops(self, source_code: str) -> list[dict]:
        """Find non-atomic read-modify-write operations on shared state.

        Returns dicts with "line", "operation", "atomic" (bool), "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        # Patterns that are inherently non-atomic in Python (GIL does NOT help
        # for compound read-modify-write on shared objects).
        non_atomic_patterns = [
            # x += 1 / x -= 1 on global / instance variables
            (r'\b\w+(?:\.\w+)?\s*\+=\s*', "compound_add_assign", False),
            (r'\b\w+(?:\.\w+)?\s*-=\s*', "compound_sub_assign", False),
            (r'\b\w+(?:\.\w+)?\s*\*=\s*', "compound_mul_assign", False),
            # dict[key] += ... — check-then-act
            (r'\w+\s*\[.+\]\s*[+\-\*\/]?=\s*', "indexed_augmented_assign", False),
            # x = x + 1 style
            (r'(\w+)\s*=\s*\1\s*[+\-\*]', "read_modify_write", False),
        ]

        # Atomic operations: collections.Counter/deque/queue.Queue operations.
        atomic_patterns = [
            (r'queue\.Queue\(\)', "queue_put_get"),
            (r'collections\.deque\(\)', "deque_appendleft"),
        ]

        def _inside_lock(lineno: int) -> bool:
            current_indent = len(lines[lineno - 1]) - len(lines[lineno - 1].lstrip())
            for i in range(lineno - 2, max(-1, lineno - 40), -1):
                l = lines[i]
                if not l.strip():
                    continue
                indent = len(l) - len(l.lstrip())
                if indent < current_indent and re.search(
                    r'\bwith\b.*\b(?:lock|Lock|RLock|mutex|_lock)\b', l, re.IGNORECASE
                ):
                    return True
            return False

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Skip comments.
            if stripped.startswith("#"):
                continue

            for pattern, op_name, is_atomic in non_atomic_patterns:
                if re.search(pattern, stripped):
                    locked = _inside_lock(lineno)
                    results.append(
                        {
                            "line": lineno,
                            "operation": op_name,
                            "atomic": locked,
                            "suggestion": (
                                "Operation is atomic (protected by lock)."
                                if locked
                                else (
                                    f"'{op_name}' is not atomic — wrap with a lock or use "
                                    "threading.Lock / atomic types from the 'atomics' package."
                                )
                            ),
                        }
                    )
                    break  # one finding per line

        return results

    def verify_thread_local(self, source_code: str) -> list[dict]:
        """Check if threading.local() is used where appropriate.

        Flags per-thread state stored in module-level or instance-level
        dicts/lists that should instead use threading.local().

        Returns dicts with "line", "pattern", "uses_thread_local" (bool),
        "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()
        uses_thread_local = bool(re.search(r'threading\.local\(\)', source_code))

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # threading.local() usage — flag as good.
            if re.search(r'threading\.local\(\)', stripped):
                results.append(
                    {
                        "line": lineno,
                        "pattern": stripped,
                        "uses_thread_local": True,
                        "suggestion": "Good: threading.local() correctly isolates per-thread state.",
                    }
                )
                continue

            # Patterns that suggest per-thread state without thread-local.
            # e.g. _thread_data = {}, per_thread_cache = {}
            if re.search(
                r'(?:thread|per_thread|local_|_local)\w*\s*=\s*(?:\{\}|\[\])',
                stripped,
                re.IGNORECASE,
            ):
                results.append(
                    {
                        "line": lineno,
                        "pattern": stripped,
                        "uses_thread_local": uses_thread_local,
                        "suggestion": (
                            "Looks like per-thread state stored in a shared dict/list. "
                            "Use threading.local() to give each thread its own storage."
                        ),
                    }
                )

            # Thread-id keyed dicts: data[threading.get_ident()] = ...
            if re.search(r'threading\.get_ident\(\)', stripped):
                results.append(
                    {
                        "line": lineno,
                        "pattern": stripped,
                        "uses_thread_local": False,
                        "suggestion": (
                            "Manual thread-id keying detected. "
                            "Replace with threading.local() for simpler, safer per-thread state."
                        ),
                    }
                )

        return results
