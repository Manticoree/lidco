"""
Q343 CLI commands — /thread-safety, /deadlock-detect, /queue-guard, /resource-cleanup

Registered via register_q343_commands(registry).
"""
from __future__ import annotations


def register_q343_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q343 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /thread-safety — Runs ThreadSafetyAnalyzer on source code
    # ------------------------------------------------------------------
    async def thread_safety_handler(args: str) -> str:
        """
        Usage: /thread-safety <source-code>
               /thread-safety --help
        """
        from lidco.stability.thread_safety import ThreadSafetyAnalyzer

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /thread-safety <source-code>\n"
                "\n"
                "Analyzes Python source code for thread-safety issues:\n"
                "  - Unguarded shared mutable state\n"
                "  - Lock usage patterns (Lock, RLock, Semaphore)\n"
                "  - Non-atomic read-modify-write operations\n"
                "  - threading.local() usage verification"
            )

        source = args
        analyzer = ThreadSafetyAnalyzer()

        unguarded = analyzer.find_unguarded_state(source)
        locks = analyzer.analyze_locks(source)
        atomic_ops = analyzer.audit_atomic_ops(source)
        thread_local = analyzer.verify_thread_local(source)

        lines: list[str] = [
            "Thread Safety Analysis Report",
            "=" * 50,
        ]

        if unguarded:
            lines.append(f"\nUnguarded shared state ({len(unguarded)} issues):")
            for u in unguarded:
                lines.append(
                    f"  Line {u['line']}: '{u['variable']}' — {u['issue']}\n"
                    f"    Suggestion: {u['suggestion']}"
                )
        else:
            lines.append("\nNo unguarded shared state detected.")

        if locks:
            lock_issues = [l for l in locks if l["issues"]]
            lines.append(f"\nLock analysis ({len(locks)} locks found, {len(lock_issues)} with issues):")
            for lk in locks:
                issue_str = "; ".join(lk["issues"]) if lk["issues"] else "OK"
                lines.append(
                    f"  Line {lk['line']}: [{lk['lock_type']}] {lk['usage']} — {issue_str}"
                )
        else:
            lines.append("\nNo lock usage detected.")

        non_atomic = [a for a in atomic_ops if not a["atomic"]]
        if non_atomic:
            lines.append(f"\nNon-atomic operations ({len(non_atomic)}):")
            for op in non_atomic:
                lines.append(
                    f"  Line {op['line']}: [{op['operation']}] — {op['suggestion']}"
                )
        else:
            lines.append(f"\nAtomic ops check: {len(atomic_ops)} operations scanned, all safe.")

        tl_issues = [t for t in thread_local if not t["uses_thread_local"]]
        if tl_issues:
            lines.append(f"\nthread_local suggestions ({len(tl_issues)}):")
            for t in tl_issues:
                lines.append(
                    f"  Line {t['line']}: {t['suggestion']}"
                )
        else:
            lines.append(f"\nThread-local checks: {len(thread_local)} patterns scanned.")

        total_issues = len(unguarded) + sum(1 for l in locks if l["issues"]) + len(non_atomic) + len(tl_issues)
        lines.append(f"\nTotal issues: {total_issues}")
        return "\n".join(lines)

    registry.register_async(
        "thread-safety",
        "Analyze source code for thread-safety issues: unguarded state, locks, atomic ops",
        thread_safety_handler,
    )

    # ------------------------------------------------------------------
    # /deadlock-detect — Runs AsyncDeadlockDetector on source code
    # ------------------------------------------------------------------
    async def deadlock_detect_handler(args: str) -> str:
        """
        Usage: /deadlock-detect <source-code>
               /deadlock-detect --help
        """
        from lidco.stability.deadlock_detect import AsyncDeadlockDetector

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /deadlock-detect <source-code>\n"
                "\n"
                "Detects potential async deadlocks:\n"
                "  - Nested awaits on same lock in same coroutine\n"
                "  - Blocking calls inside async functions\n"
                "  - Inconsistent resource acquisition order\n"
                "  - Async operations without timeouts"
            )

        source = args
        detector = AsyncDeadlockDetector()

        deadlocks = detector.detect_deadlocks(source)
        await_chains = detector.analyze_await_chains(source)
        ordering = detector.check_resource_ordering(source)
        timeouts = detector.verify_timeouts(source)

        lines: list[str] = [
            "Async Deadlock Detection Report",
            "=" * 50,
        ]

        if deadlocks:
            lines.append(f"\nPotential deadlocks ({len(deadlocks)}):")
            for d in deadlocks:
                loc = f"Line {d['line']}: " if d["line"] else ""
                lines.append(
                    f"  {loc}[{d['risk']}] {d['pattern']}\n"
                    f"    {d['description']}"
                )
        else:
            lines.append("\nNo potential deadlocks detected.")

        if await_chains:
            lines.append(f"\nBlocking calls in async code ({len(await_chains)}):")
            for a in await_chains:
                lines.append(
                    f"  Line {a['line']} (in {a['chain']}): {a['issue']}\n"
                    f"    Suggestion: {a['suggestion']}"
                )
        else:
            lines.append("\nNo blocking calls in async functions detected.")

        ordering_issues = [o for o in ordering if not o["ordering_consistent"]]
        if ordering_issues:
            lines.append(f"\nInconsistent resource ordering ({len(ordering_issues)}):")
            for o in ordering_issues:
                lines.append(f"  Resources {o['resources']}: {o['suggestion']}")
        else:
            lines.append(f"\nResource ordering: {len(ordering)} pairs checked.")

        missing_timeouts = [t for t in timeouts if not t["has_timeout"]]
        if missing_timeouts:
            lines.append(f"\nMissing timeouts ({len(missing_timeouts)}):")
            for t in missing_timeouts:
                lines.append(
                    f"  Line {t['line']}: '{t['operation']}' — {t['suggestion']}"
                )
        else:
            lines.append(f"\nTimeout checks: {len(timeouts)} operations checked.")

        total_issues = len(deadlocks) + len(await_chains) + len(ordering_issues) + len(missing_timeouts)
        lines.append(f"\nTotal issues: {total_issues}")
        return "\n".join(lines)

    registry.register_async(
        "deadlock-detect",
        "Detect potential async deadlocks, blocking calls, resource ordering, and timeout gaps",
        deadlock_detect_handler,
    )

    # ------------------------------------------------------------------
    # /queue-guard — Runs QueueOverflowGuard checks
    # ------------------------------------------------------------------
    async def queue_guard_handler(args: str) -> str:
        """
        Usage: /queue-guard <source-code>
               /queue-guard --help
        """
        from lidco.stability.queue_guard import QueueOverflowGuard

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /queue-guard <source-code>\n"
                "\n"
                "Checks queue safety in source code:\n"
                "  - Queues without maxsize (unbounded)\n"
                "  - Reports findings with suggestions"
            )

        source = args
        guard = QueueOverflowGuard()

        overflow = guard.check_overflow_prevention(source)

        lines: list[str] = [
            "Queue Overflow Guard Report",
            "=" * 50,
        ]

        if overflow:
            no_maxsize = [q for q in overflow if not q["has_maxsize"]]
            with_maxsize = [q for q in overflow if q["has_maxsize"]]
            if no_maxsize:
                lines.append(f"\nUnbounded queues ({len(no_maxsize)}):")
                for q in no_maxsize:
                    lines.append(
                        f"  Line {q['line']}: [{q['queue_type']}] — {q['suggestion']}"
                    )
            if with_maxsize:
                lines.append(f"\nBounded queues ({len(with_maxsize)}) — OK:")
                for q in with_maxsize:
                    lines.append(f"  Line {q['line']}: [{q['queue_type']}]")
        else:
            lines.append("\nNo queue instantiations found.")

        total_issues = sum(1 for q in overflow if not q["has_maxsize"])
        lines.append(f"\nTotal issues: {total_issues}")
        return "\n".join(lines)

    registry.register_async(
        "queue-guard",
        "Check queue overflow prevention: maxsize bounds, unbounded queue detection",
        queue_guard_handler,
    )

    # ------------------------------------------------------------------
    # /resource-cleanup — Runs ResourceCleanupValidator on source code
    # ------------------------------------------------------------------
    async def resource_cleanup_handler(args: str) -> str:
        """
        Usage: /resource-cleanup <source-code>
               /resource-cleanup --help
        """
        from lidco.stability.resource_cleanup import ResourceCleanupValidator

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /resource-cleanup <source-code>\n"
                "\n"
                "Validates resource cleanup in Python source code:\n"
                "  - File handles (open without context manager)\n"
                "  - Network/DB connections without close\n"
                "  - Temp directories without cleanup\n"
                "  - __del__ method correctness"
            )

        source = args
        validator = ResourceCleanupValidator()

        file_handles = validator.check_file_handles(source)
        connections = validator.check_connections(source)
        temp_dirs = validator.check_temp_dirs(source)
        del_methods = validator.audit_del_methods(source)

        lines: list[str] = [
            "Resource Cleanup Validation Report",
            "=" * 50,
        ]

        bad_files = [f for f in file_handles if not f["uses_context_manager"]]
        if bad_files:
            lines.append(f"\nFile handle issues ({len(bad_files)}):")
            for f in bad_files:
                lines.append(
                    f"  Line {f['line']}: {f['suggestion']}"
                )
        else:
            lines.append(f"\nFile handles: {len(file_handles)} checked, all OK.")

        bad_conn = [c for c in connections if not c["has_cleanup"]]
        if bad_conn:
            lines.append(f"\nConnection issues ({len(bad_conn)}):")
            for c in bad_conn:
                lines.append(
                    f"  Line {c['line']}: [{c['connection_type']}] — {c['suggestion']}"
                )
        else:
            lines.append(f"\nConnections: {len(connections)} checked, all OK.")

        bad_temp = [t for t in temp_dirs if not t["has_cleanup"]]
        if bad_temp:
            lines.append(f"\nTemp directory issues ({len(bad_temp)}):")
            for t in bad_temp:
                lines.append(
                    f"  Line {t['line']}: {t['suggestion']}"
                )
        else:
            lines.append(f"\nTemp dirs: {len(temp_dirs)} checked, all OK.")

        del_issues = [d for d in del_methods if d["issues"]]
        if del_issues:
            lines.append(f"\n__del__ method issues ({len(del_issues)}):")
            for d in del_issues:
                issue_str = "; ".join(d["issues"])
                lines.append(
                    f"  Line {d['line']} (class {d['class_name']}): {issue_str}\n"
                    f"    Suggestion: {d['suggestion']}"
                )
        else:
            lines.append(f"\n__del__ methods: {len(del_methods)} checked, all OK.")

        total_issues = len(bad_files) + len(bad_conn) + len(bad_temp) + len(del_issues)
        lines.append(f"\nTotal issues: {total_issues}")
        return "\n".join(lines)

    registry.register_async(
        "resource-cleanup",
        "Validate resource cleanup: file handles, connections, temp dirs, __del__ methods",
        resource_cleanup_handler,
    )
