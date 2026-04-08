"""
Async Deadlock Detector — Q343.

Detects potential async deadlocks, analyzes await chains for blocking
operations, checks resource acquisition ordering, and verifies timeouts.
"""
from __future__ import annotations

import re


class AsyncDeadlockDetector:
    """Detect potential deadlock patterns in async Python source code."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_deadlocks(self, source_code: str) -> list[dict]:
        """Find potential async deadlocks.

        Looks for:
        - Nested awaits on the same asyncio.Lock within the same coroutine.
        - Circular acquire patterns across async functions.

        Returns dicts with "line", "pattern", "risk" (HIGH/MEDIUM/LOW),
        "description".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        # Track asyncio.Lock / asyncio.Semaphore variables.
        lock_vars: set[str] = set()
        for line in lines:
            m = re.search(
                r'(\w+)\s*=\s*asyncio\.(Lock|Semaphore|BoundedSemaphore|Event|Condition)\(\)',
                line,
            )
            if m:
                lock_vars.add(m.group(1))

        # Within each async def block, find duplicate awaits on the same lock.
        current_func_locks: list[str] = []
        inside_async = False
        async_indent = 0

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            current_indent = len(line) - len(line.lstrip())

            if re.match(r'async\s+def\s+\w+', stripped):
                inside_async = True
                async_indent = current_indent
                current_func_locks = []
                continue

            if inside_async and current_indent <= async_indent and stripped and not stripped.startswith("#"):
                # Left the async function.
                inside_async = False
                current_func_locks = []

            if inside_async:
                # Detect: await lock.acquire()
                for var in lock_vars:
                    if re.search(rf'await\s+{re.escape(var)}\s*\.\s*acquire\s*\(', stripped):
                        if var in current_func_locks:
                            results.append(
                                {
                                    "line": lineno,
                                    "pattern": f"double_acquire:{var}",
                                    "risk": "HIGH",
                                    "description": (
                                        f"'{var}.acquire()' awaited twice in the same coroutine "
                                        "without a matching release — this will deadlock."
                                    ),
                                }
                            )
                        else:
                            current_func_locks.append(var)

                # Detect async with on the same lock twice (nested context managers).
                for var in lock_vars:
                    if re.search(rf'async\s+with\s+{re.escape(var)}\b', stripped):
                        if var in current_func_locks:
                            results.append(
                                {
                                    "line": lineno,
                                    "pattern": f"nested_async_with:{var}",
                                    "risk": "HIGH",
                                    "description": (
                                        f"Nested 'async with {var}' in the same coroutine — "
                                        "asyncio.Lock is not reentrant; use asyncio.Condition "
                                        "or restructure to avoid re-entry."
                                    ),
                                }
                            )
                        else:
                            current_func_locks.append(var)

        # Circular dependency heuristic: func A awaits func B which awaits func A.
        # Simple 2-hop check using call graph patterns.
        func_calls: dict[str, list[str]] = {}
        current_fn: str | None = None
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            m = re.match(r'async\s+def\s+(\w+)\s*\(', stripped)
            if m:
                current_fn = m.group(1)
                func_calls[current_fn] = []
                continue
            if current_fn:
                for called in re.findall(r'\bawait\s+(\w+)\s*\(', stripped):
                    func_calls[current_fn].append(called)

        for fn_a, callees_a in func_calls.items():
            for fn_b in callees_a:
                if fn_b in func_calls and fn_a in func_calls.get(fn_b, []):
                    results.append(
                        {
                            "line": 0,
                            "pattern": f"circular_await:{fn_a}<->{fn_b}",
                            "risk": "MEDIUM",
                            "description": (
                                f"Potential circular await: '{fn_a}' awaits '{fn_b}' "
                                f"which awaits '{fn_a}' — verify no shared lock is held "
                                "across both calls."
                            ),
                        }
                    )

        return results

    def analyze_await_chains(self, source_code: str) -> list[dict]:
        """Trace await chains and find potentially blocking operations.

        Returns dicts with "line", "chain", "issue", "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        blocking_patterns = [
            (r'\btime\.sleep\s*\(', "time.sleep() in async context", "Use 'await asyncio.sleep()' instead."),
            (r'\bos\.system\s*\(', "os.system() blocks the event loop", "Use asyncio.create_subprocess_exec() instead."),
            (r'\bsubprocess\.(?:call|run|check_output|Popen)\s*\(', "subprocess call blocks event loop",
             "Use asyncio.create_subprocess_exec() or run_in_executor()."),
            (r'\bopen\s*\(.*\)', "synchronous file I/O blocks event loop",
             "Use aiofiles or run_in_executor() for file operations."),
            (r'\brequests\.\w+\s*\(', "requests library is synchronous",
             "Use aiohttp or httpx with async/await instead."),
            (r'\binput\s*\(', "input() blocks the event loop",
             "Use asyncio.get_event_loop().run_in_executor(None, input) or aioconsole."),
        ]

        inside_async = False
        async_indent = 0
        async_func_name = ""

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            current_indent = len(line) - len(line.lstrip())

            m = re.match(r'async\s+def\s+(\w+)', stripped)
            if m:
                inside_async = True
                async_indent = current_indent
                async_func_name = m.group(1)
                continue

            if inside_async and current_indent <= async_indent and stripped and not stripped.startswith("#"):
                if not re.match(r'async\s+def|def\s+', stripped):
                    pass  # could be decorator or something — keep going
                if re.match(r'(?:def|class|async\s+def)\s+', stripped) and not re.match(r'async\s+def\s+', stripped):
                    inside_async = False
                    async_func_name = ""
                    continue

            if inside_async:
                for pattern, issue, suggestion in blocking_patterns:
                    if re.search(pattern, stripped):
                        results.append(
                            {
                                "line": lineno,
                                "chain": async_func_name,
                                "issue": issue,
                                "suggestion": suggestion,
                            }
                        )
                        break  # one finding per line

        return results

    def check_resource_ordering(self, source_code: str) -> list[dict]:
        """Verify resources are acquired in consistent order.

        Detects cases where two coroutines acquire the same set of locks
        in different orders (classic deadlock condition).

        Returns dicts with "resources", "ordering_consistent" (bool),
        "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        # Build per-function lock acquisition order.
        func_lock_order: dict[str, list[str]] = {}
        current_fn: str | None = None
        current_fn_indent = 0

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            current_indent = len(line) - len(line.lstrip())

            m = re.match(r'(?:async\s+)?def\s+(\w+)\s*\(', stripped)
            if m:
                current_fn = m.group(1)
                current_fn_indent = current_indent
                func_lock_order[current_fn] = []
                continue

            if current_fn is not None:
                if current_indent <= current_fn_indent and stripped and not stripped.startswith("#"):
                    if not re.match(r'(?:async\s+)?def\s+\w+', stripped):
                        current_fn = None
                        continue

            if current_fn:
                # Detect 'with lock_name:' or 'await lock_name.acquire()'
                for pattern in [
                    r'(?:async\s+)?with\s+(\w+)\s*(?:,|\:)',
                    r'await\s+(\w+)\s*\.\s*acquire\s*\(',
                    r'(\w+)\s*\.\s*acquire\s*\(',
                ]:
                    m2 = re.search(pattern, stripped)
                    if m2:
                        lock_name = m2.group(1)
                        # Ignore 'self', 'cls', common non-lock names.
                        if lock_name not in {"self", "cls", "loop", "asyncio"}:
                            func_lock_order[current_fn].append(lock_name)

        # Compare ordering across function pairs.
        fn_names = list(func_lock_order.keys())
        for i in range(len(fn_names)):
            for j in range(i + 1, len(fn_names)):
                fn_a, fn_b = fn_names[i], fn_names[j]
                order_a = func_lock_order[fn_a]
                order_b = func_lock_order[fn_b]
                shared = [r for r in order_a if r in order_b]
                if len(shared) < 2:
                    continue

                # Check if the shared resources appear in the same order.
                idx_a = [order_a.index(r) for r in shared]
                idx_b = [order_b.index(r) for r in shared]
                consistent = idx_a == sorted(idx_a) and idx_b == sorted(idx_b)
                # Detect a reversal specifically.
                if sorted(idx_a) != sorted(idx_b):
                    consistent = True  # different sets — can't compare
                else:
                    consistent = (
                        [order_a[i] for i in sorted(range(len(idx_a)), key=lambda x: idx_a[x])]
                        ==
                        [order_b[i] for i in sorted(range(len(idx_b)), key=lambda x: idx_b[x])]
                    )

                results.append(
                    {
                        "resources": shared,
                        "ordering_consistent": consistent,
                        "suggestion": (
                            "Resource acquisition order is consistent — low deadlock risk."
                            if consistent
                            else (
                                f"'{fn_a}' and '{fn_b}' acquire {shared} in different orders — "
                                "establish a global lock hierarchy and always acquire in the same order."
                            )
                        ),
                    }
                )

        return results

    def verify_timeouts(self, source_code: str) -> list[dict]:
        """Verify async operations have timeouts.

        Returns dicts with "line", "operation", "has_timeout" (bool),
        "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        # Patterns for async operations that should have timeouts.
        # Each tuple: (detection_pattern, label).
        timeout_ops = [
            (r'(?:await\s+)?(\w+)\s*\.\s*acquire\s*\(', "lock.acquire()"),
            (r'asyncio\.wait\s*\(', "asyncio.wait()"),
            (r'asyncio\.gather\s*\(', "asyncio.gather()"),
            (r'(?:await\s+)?(\w+)\.(?:read|write|connect|accept)\s*\(', "I/O operation"),
            (r'asyncio\.open_connection\s*\(', "asyncio.open_connection()"),
        ]

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Only inspect lines that contain an await or call one of the async patterns.
            if "await" not in stripped and "asyncio." not in stripped:
                continue

            for pattern, op_label in timeout_ops:
                if re.search(pattern, stripped):
                    # Consider it has_timeout if:
                    # - wrapped in asyncio.wait_for on the same line
                    # - timeout= kwarg present on the same line
                    # - preceding non-blank line opens asyncio.wait_for(
                    has_timeout = bool(
                        re.search(r'asyncio\.wait_for\s*\(', stripped)
                        or re.search(r'\btimeout\s*=', stripped)
                        or (
                            lineno >= 2
                            and re.search(r'asyncio\.wait_for\s*\(', lines[lineno - 2])
                        )
                    )
                    results.append(
                        {
                            "line": lineno,
                            "operation": op_label,
                            "has_timeout": has_timeout,
                            "suggestion": (
                                "Timeout is present — good."
                                if has_timeout
                                else (
                                    f"'{op_label}' has no timeout — wrap with "
                                    "asyncio.wait_for(coro, timeout=N) to prevent indefinite blocking."
                                )
                            ),
                        }
                    )
                    break  # one finding per line

        return results
