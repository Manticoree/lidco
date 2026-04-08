"""
Q339 CLI commands — /config-race, /event-loop-check, /import-cycles, /memory-leaks

Registered via register_q339_commands(registry).
"""
from __future__ import annotations

import json
import shlex


def register_q339_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q339 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /config-race — Detect race conditions in config access
    # ------------------------------------------------------------------
    async def config_race_handler(args: str) -> str:
        """
        Usage: /config-race <source-code>
               /config-race --file <path>
        """
        from lidco.stability.config_race import ConfigRaceDetector

        parts = shlex.split(args) if args.strip() else []

        source: str = ""
        if not parts:
            return (
                "Usage: /config-race <source-code-snippet>\n"
                "       /config-race --file <path>"
            )

        if parts[0] == "--file":
            if len(parts) < 2:
                return "Usage: /config-race --file <path>"
            try:
                with open(parts[1], encoding="utf-8") as fh:
                    source = fh.read()
            except OSError as exc:
                return f"Error reading file: {exc}"
        else:
            source = args

        detector = ConfigRaceDetector()
        races = detector.detect_races(source)
        contentions = detector.analyze_lock_contention(source)
        deadlocks = detector.detect_deadlocks(source)
        fixes = detector.suggest_fixes(races)

        lines = [
            f"Config Race Analysis:",
            f"  Race conditions : {len(races)}",
            f"  Lock contentions: {len(contentions)}",
            f"  Deadlock risks  : {len(deadlocks)}",
        ]

        if races:
            lines.append("")
            lines.append("Race Conditions:")
            for r in races[:10]:
                lines.append(
                    f"  [{r['severity']}] Line {r['line']}: {r['description']}"
                )

        if deadlocks:
            lines.append("")
            lines.append("Deadlock Risks:")
            for d in deadlocks[:5]:
                lines.append(f"  Locks: {d['locks']}")
                lines.append(f"  {d['description']}")
                lines.append(f"  Fix: {d['fix']}")

        if fixes:
            lines.append("")
            lines.append("Suggested Fixes:")
            for fix in fixes:
                lines.append(f"  {fix}")

        return "\n".join(lines)

    registry.register_async(
        "config-race",
        "Detect race conditions in config access code",
        config_race_handler,
    )

    # ------------------------------------------------------------------
    # /event-loop-check — Check for asyncio anti-patterns
    # ------------------------------------------------------------------
    async def event_loop_check_handler(args: str) -> str:
        """
        Usage: /event-loop-check <source-code-snippet>
               /event-loop-check --file <path>
               /event-loop-check --test <path>   (test isolation mode)
        """
        from lidco.stability.event_loop_guard import EventLoopGuard

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /event-loop-check <source-code-snippet>\n"
                "       /event-loop-check --file <path>\n"
                "       /event-loop-check --test <path>"
            )

        test_mode = False
        source: str = ""

        if parts[0] in ("--file", "--test"):
            if len(parts) < 2:
                return f"Usage: /event-loop-check {parts[0]} <path>"
            test_mode = parts[0] == "--test"
            try:
                with open(parts[1], encoding="utf-8") as fh:
                    source = fh.read()
            except OSError as exc:
                return f"Error reading file: {exc}"
        else:
            source = args

        guard = EventLoopGuard()
        conflicts = guard.check_loop_conflicts(source)
        deprecations = guard.enforce_asyncio_run(source)
        cleanup = guard.check_loop_cleanup(source)
        isolation = guard.check_isolation(source) if test_mode else []

        lines = [
            "Event Loop Analysis:",
            f"  Conflicts    : {len(conflicts)}",
            f"  Deprecations : {len(deprecations)}",
            f"  Cleanup issues: {len(cleanup)}",
        ]
        if test_mode:
            lines.append(f"  Isolation issues: {len(isolation)}")

        if conflicts:
            lines.append("")
            lines.append("Loop Conflicts:")
            for c in conflicts[:5]:
                lines.append(f"  Line {c['line']}: {c['issue']}")
                lines.append(f"    Fix: {c['fix']}")

        if deprecations:
            lines.append("")
            lines.append("Deprecated Patterns:")
            for d in deprecations[:5]:
                lines.append(f"  Line {d['line']}: {d['old_pattern']} -> {d['new_pattern']}")

        if cleanup:
            lines.append("")
            lines.append("Cleanup Issues:")
            for cl in cleanup[:5]:
                lines.append(f"  Line {cl['line']}: {cl['issue']}")
                lines.append(f"    Suggestion: {cl['suggestion']}")

        if isolation:
            lines.append("")
            lines.append("Test Isolation Issues:")
            for iso in isolation[:5]:
                lines.append(f"  Line {iso['line']}: {iso['issue']}")
                lines.append(f"    Fix: {iso['fix']}")

        return "\n".join(lines)

    registry.register_async(
        "event-loop-check",
        "Check source code for asyncio event-loop anti-patterns",
        event_loop_check_handler,
    )

    # ------------------------------------------------------------------
    # /import-cycles — Detect import cycles from a JSON graph
    # ------------------------------------------------------------------
    async def import_cycles_handler(args: str) -> str:
        """
        Usage: /import-cycles <json-graph>
               /import-cycles --file <path>

        The JSON graph is a dict mapping module names to lists of imports:
          {"a": ["b", "c"], "b": ["a"]}
        """
        from lidco.stability.import_cycles import ImportCycleDetector

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                'Usage: /import-cycles \'{"mod_a": ["mod_b"], "mod_b": ["mod_a"]}\'\n'
                "       /import-cycles --file <path>"
            )

        raw: str = ""
        if parts[0] == "--file":
            if len(parts) < 2:
                return "Usage: /import-cycles --file <path>"
            try:
                with open(parts[1], encoding="utf-8") as fh:
                    raw = fh.read()
            except OSError as exc:
                return f"Error reading file: {exc}"
        else:
            raw = args

        try:
            modules: dict = json.loads(raw)
        except json.JSONDecodeError as exc:
            return f"Error: invalid JSON graph — {exc}"

        if not isinstance(modules, dict):
            return "Error: JSON must be a dict mapping module names to import lists."

        detector = ImportCycleDetector()
        detector.build_graph(modules)
        cycles = detector.detect_cycles()
        suggestions = detector.suggest_breaks(cycles)

        lines = [
            "Import Cycle Analysis:",
            f"  Modules : {len(modules)}",
            f"  Cycles  : {len(cycles)}",
        ]

        if not cycles:
            lines.append("  No import cycles detected.")
        else:
            lines.append("")
            lines.append("Detected Cycles:")
            for i, cycle in enumerate(cycles, start=1):
                lines.append(f"  Cycle {i}: {' -> '.join(cycle)} -> {cycle[0]}")

            lines.append("")
            lines.append("Break Suggestions:")
            for s in suggestions:
                lines.append(f"  Break at '{s['break_point']}': {s['suggestion'][:120]}")

        return "\n".join(lines)

    registry.register_async(
        "import-cycles",
        "Detect import cycles from a JSON dependency graph",
        import_cycles_handler,
    )

    # ------------------------------------------------------------------
    # /memory-leaks — Scan source code for memory leak patterns
    # ------------------------------------------------------------------
    async def memory_leaks_handler(args: str) -> str:
        """
        Usage: /memory-leaks <source-code-snippet>
               /memory-leaks --file <path>
               /memory-leaks --threshold <mb>  (check current process memory)
        """
        from lidco.stability.leak_scanner import LeakScanner

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /memory-leaks <source-code-snippet>\n"
                "       /memory-leaks --file <path>\n"
                "       /memory-leaks --threshold <mb>"
            )

        threshold_mb = 50.0
        source: str = ""
        threshold_check_only = False

        if parts[0] == "--threshold":
            if len(parts) < 2:
                return "Usage: /memory-leaks --threshold <mb>"
            try:
                threshold_mb = float(parts[1])
            except ValueError:
                return "Error: threshold must be a number (MB)."
            threshold_check_only = True
        elif parts[0] == "--file":
            if len(parts) < 2:
                return "Usage: /memory-leaks --file <path>"
            try:
                with open(parts[1], encoding="utf-8") as fh:
                    source = fh.read()
            except OSError as exc:
                return f"Error reading file: {exc}"
            # Optional threshold override.
            for i, p in enumerate(parts[2:], start=2):
                if p == "--threshold" and i + 1 < len(parts):
                    try:
                        threshold_mb = float(parts[i + 1])
                    except ValueError:
                        pass
        else:
            source = args

        scanner = LeakScanner(threshold_mb=threshold_mb)

        if threshold_check_only:
            # Runtime memory check using gc stats.
            gc_stats = scanner.get_gc_stats()
            lines = [
                "GC Stats:",
                f"  Collections   : {gc_stats['collections']}",
                f"  Collected     : {gc_stats['collected']}",
                f"  Uncollectable : {gc_stats['uncollectable']}",
                f"  Threshold     : {gc_stats['threshold']}",
            ]
            return "\n".join(lines)

        refs = scanner.scan_references(source)
        weak_refs = scanner.audit_weak_refs(source)
        gc_stats = scanner.get_gc_stats()

        lines = [
            "Memory Leak Analysis:",
            f"  Reference issues : {len(refs)}",
            f"  Weak-ref audits  : {len(weak_refs)}",
            f"  GC uncollectable : {gc_stats['uncollectable']}",
        ]

        if refs:
            lines.append("")
            lines.append("Reference Cycle Risks:")
            for r in refs[:8]:
                lines.append(f"  [{r['risk']}] Line {r['line']}: {r['description']}")

        if weak_refs:
            lines.append("")
            lines.append("Weak-ref Opportunities:")
            for w in weak_refs[:5]:
                lines.append(f"  Line {w['line']}: {w['suggestion']}")

        return "\n".join(lines)

    registry.register_async(
        "memory-leaks",
        "Scan source code for memory leak and reference-cycle patterns",
        memory_leaks_handler,
    )
