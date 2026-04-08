"""
Event loop guard — Q339.

Detects asyncio anti-patterns: deprecated loop APIs, nested loops, missing
cleanup, and test-isolation issues.
"""
from __future__ import annotations

import re


class EventLoopGuard:
    """Inspect Python source for event-loop misuse patterns."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_loop_conflicts(self, source_code: str) -> list[dict]:
        """Detect conflicts between get_event_loop() and asyncio.run() usage.

        Returns dicts with "line", "issue", "fix".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        has_asyncio_run = any(re.search(r"asyncio\.run\(", l) for l in lines)
        has_get_loop = any(
            re.search(r"(?:asyncio\.)?get_event_loop\(\)", l) for l in lines
        )

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Mixing get_event_loop with asyncio.run in same file.
            if re.search(r"(?:asyncio\.)?get_event_loop\(\)", stripped):
                issue = "get_event_loop() used"
                fix = "Use asyncio.run() instead of get_event_loop().run_until_complete()"
                if has_asyncio_run:
                    issue += " alongside asyncio.run() — mixing deprecated and modern API"
                results.append({"line": lineno, "issue": issue, "fix": fix})

            # Nested asyncio.run() calls — forbidden.
            # Only flag when the current line is indented inside an async def block.
            if re.search(r"asyncio\.run\(", stripped):
                current_indent = len(line) - len(line.lstrip())
                # Look backwards for an async def at a lower indentation level.
                inside_async = False
                for prev_line in reversed(lines[: lineno - 1]):
                    prev_indent = len(prev_line) - len(prev_line.lstrip()) if prev_line.strip() else current_indent
                    if prev_indent < current_indent and re.search(r"async\s+def\s+\w+", prev_line):
                        inside_async = True
                        break
                    # Hit a block at same or lower indent that is NOT async def — stop.
                    if prev_indent <= current_indent and prev_line.strip() and not prev_line.strip().startswith("#"):
                        if not re.search(r"async\s+def\s+\w+", prev_line):
                            break
                if inside_async:
                    results.append(
                        {
                            "line": lineno,
                            "issue": (
                                "asyncio.run() called inside an async function — "
                                "nested event loops are not supported"
                            ),
                            "fix": "Use 'await coro()' directly instead of asyncio.run().",
                        }
                    )

            # loop.run_until_complete() — deprecated pattern.
            if re.search(r"\.run_until_complete\(", stripped):
                results.append(
                    {
                        "line": lineno,
                        "issue": "loop.run_until_complete() is deprecated and error-prone",
                        "fix": "Replace with asyncio.run(coro()) at the top-level entry point.",
                    }
                )

        return results

    def enforce_asyncio_run(self, source_code: str) -> list[dict]:
        """Find deprecated loop patterns that should be replaced by asyncio.run().

        Returns dicts with "line", "old_pattern", "new_pattern".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        replacements = [
            (
                r"((?:asyncio\.)?get_event_loop\(\)\.run_until_complete\()(.+)(\))",
                "asyncio.run({coro})",
                "loop.run_until_complete(coro)",
            ),
            (
                r"loop\s*=\s*asyncio\.get_event_loop\(\)",
                "asyncio.run(main())",
                "loop = asyncio.get_event_loop()",
            ),
            (
                r"asyncio\.get_event_loop\(\)\.run_forever\(\)",
                "asyncio.run(main())",
                "asyncio.get_event_loop().run_forever()",
            ),
            (
                r"loop\.close\(\)",
                "# no explicit close needed with asyncio.run()",
                "loop.close()",
            ),
            (
                r"asyncio\.get_event_loop\(\)\.close\(\)",
                "# no explicit close needed with asyncio.run()",
                "asyncio.get_event_loop().close()",
            ),
        ]

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            for pattern, new_pat, old_desc in replacements:
                if re.search(pattern, stripped):
                    results.append(
                        {
                            "line": lineno,
                            "old_pattern": old_desc,
                            "new_pattern": new_pat,
                        }
                    )
                    break  # one replacement per line

        return results

    def check_loop_cleanup(self, source_code: str) -> list[dict]:
        """Verify proper event loop cleanup in source code.

        Returns dicts with "line", "issue", "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Explicit loop creation without corresponding close.
            if re.search(r"asyncio\.new_event_loop\(\)", stripped):
                # Check if close is present anywhere nearby (± 30 lines).
                window = lines[lineno : min(len(lines), lineno + 30)]
                has_close = any(re.search(r"\.close\(\)", l) for l in window)
                if not has_close:
                    results.append(
                        {
                            "line": lineno,
                            "issue": (
                                "asyncio.new_event_loop() created but .close() "
                                "not found in the following 30 lines"
                            ),
                            "suggestion": (
                                "Always close manually created loops in a "
                                "try/finally block or use asyncio.run() instead."
                            ),
                        }
                    )

            # set_event_loop without cleanup.
            if re.search(r"asyncio\.set_event_loop\(", stripped):
                results.append(
                    {
                        "line": lineno,
                        "issue": (
                            "asyncio.set_event_loop() sets a global loop — "
                            "may cause cross-test pollution"
                        ),
                        "suggestion": (
                            "Reset the loop with asyncio.set_event_loop(None) "
                            "in teardown, or use asyncio.run() which manages "
                            "the loop automatically."
                        ),
                    }
                )

            # Unguarded loop.run_forever() without stop mechanism.
            if re.search(r"\.run_forever\(\)", stripped):
                window = lines[max(0, lineno - 10) : lineno + 10]
                has_stop = any(re.search(r"\.stop\(\)", l) for l in window)
                if not has_stop:
                    results.append(
                        {
                            "line": lineno,
                            "issue": "run_forever() without a visible stop() call",
                            "suggestion": (
                                "Register a signal handler that calls loop.stop() "
                                "or restructure as asyncio.run(main())."
                            ),
                        }
                    )

        return results

    def check_isolation(self, test_source: str) -> list[dict]:
        """Check test files for event loop isolation issues.

        Returns dicts with "line", "issue", "fix".
        """
        results: list[dict] = []
        lines = test_source.splitlines()

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Deprecated run_until_complete in tests.
            if re.search(r"get_event_loop\(\)\.run_until_complete\(", stripped):
                results.append(
                    {
                        "line": lineno,
                        "issue": (
                            "get_event_loop().run_until_complete() in test — "
                            "fails when the loop is closed by a previous test"
                        ),
                        "fix": "Use asyncio.run(coro()) for isolated event loop per test.",
                    }
                )

            # Shared loop stored as class-level attribute.
            if re.search(r"cls\.loop\s*=\s*asyncio", stripped):
                results.append(
                    {
                        "line": lineno,
                        "issue": (
                            "Shared event loop on class — leaks loop state "
                            "between test methods"
                        ),
                        "fix": (
                            "Create a fresh loop per test or use asyncio.run() "
                            "which creates an isolated loop each time."
                        ),
                    }
                )

            # setUp creating a loop without tearDown close.
            if re.search(r"def setUp", stripped):
                window_end = min(len(lines), lineno + 15)
                setup_block = "\n".join(lines[lineno : window_end])
                if re.search(r"new_event_loop\(\)", setup_block):
                    # Check tearDown block for close.
                    full = test_source
                    teardown_m = re.search(r"def tearDown.*?(?=\n    def |\Z)", full, re.DOTALL)
                    if teardown_m and ".close()" not in teardown_m.group():
                        results.append(
                            {
                                "line": lineno,
                                "issue": (
                                    "setUp creates a new_event_loop() but tearDown "
                                    "does not appear to close it"
                                ),
                                "fix": "Call self.loop.close() in tearDown.",
                            }
                        )

            # asyncio.run inside async test helper — nesting issue.
            if re.search(r"async\s+def\s+test_", stripped):
                window_end = min(len(lines), lineno + 20)
                body = "\n".join(lines[lineno : window_end])
                if re.search(r"asyncio\.run\(", body):
                    results.append(
                        {
                            "line": lineno,
                            "issue": (
                                "asyncio.run() inside async test function — "
                                "will raise 'This event loop is already running'"
                            ),
                            "fix": (
                                "Await the coroutine directly instead of calling "
                                "asyncio.run() inside an async function."
                            ),
                        }
                    )

        return results
