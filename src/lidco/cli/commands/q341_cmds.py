"""
Q341 CLI commands — /test-isolation, /mock-check, /test-order, /perf-guard

Registered via register_q341_commands(registry).
"""
from __future__ import annotations

import json


def register_q341_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q341 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /test-isolation — Detect shared state and isolation problems
    # ------------------------------------------------------------------
    async def test_isolation_handler(args: str) -> str:
        """
        Usage: /test-isolation <python-source-code>
               /test-isolation --help
        """
        from lidco.stability.test_isolation import TestIsolationEnforcer

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /test-isolation <python-source-code>\n"
                "\n"
                "Analyzes Python test source for isolation problems:\n"
                "  - Shared mutable module/class state\n"
                "  - Global mutations (os.environ, sys.path)\n"
                "  - Fixture resource leaks\n"
                "  - Missing setUp/tearDown pairs"
            )

        source = args
        enforcer = TestIsolationEnforcer()

        shared = enforcer.find_shared_state(source)
        mutations = enforcer.find_global_mutations(source)
        leaks = enforcer.detect_fixture_leaks(source)
        cleanup = enforcer.verify_cleanup(source)

        lines: list[str] = [
            "Test Isolation Report",
            "=" * 50,
        ]

        if shared:
            lines.append(f"\nShared state ({len(shared)} found):")
            for item in shared:
                lines.append(
                    f"  Line {item['line']}: '{item['variable']}' "
                    f"[{item['type']}] risk={item['risk']}"
                )
        else:
            lines.append("\nNo shared mutable state detected.")

        if mutations:
            lines.append(f"\nGlobal mutations ({len(mutations)} found):")
            for item in mutations:
                lines.append(
                    f"  Line {item['line']}: {item['target']} "
                    f"[{item['mutation_type']}] — {item['suggestion']}"
                )
        else:
            lines.append("No global mutations detected.")

        if leaks:
            lines.append(f"\nFixture leaks ({len(leaks)} found):")
            for item in leaks:
                lines.append(
                    f"  Line {item['line']}: '{item['fixture_name']}' — "
                    f"{item['issue']}. Fix: {item['fix']}"
                )
        else:
            lines.append("No fixture leaks detected.")

        missing_cleanup = [c for c in cleanup if c["status"] == "missing_cleanup"]
        if missing_cleanup:
            lines.append(f"\nCleanup issues ({len(missing_cleanup)} found):")
            for item in missing_cleanup:
                lines.append(
                    f"  Line {item['line']}: {item['method']} — {item['suggestion']}"
                )
        else:
            lines.append("setUp/tearDown pairing OK.")

        total = len(shared) + len(mutations) + len(leaks) + len(missing_cleanup)
        lines.append(f"\nTotal issues: {total}")
        return "\n".join(lines)

    registry.register_async(
        "test-isolation",
        "Detect shared state, global mutations, fixture leaks, and cleanup issues",
        test_isolation_handler,
    )

    # ------------------------------------------------------------------
    # /mock-check — Check mock integrity in test source
    # ------------------------------------------------------------------
    async def mock_check_handler(args: str) -> str:
        """
        Usage: /mock-check <python-source-code>
               /mock-check --help
        """
        from lidco.stability.mock_checker import MockIntegrityChecker

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /mock-check <python-source-code>\n"
                "\n"
                "Checks mock integrity in test source:\n"
                "  - Signature drift (return_value mismatches)\n"
                "  - Unused mocks\n"
                "  - Over-mocking (>5 mocks per test)"
            )

        source = args
        checker = MockIntegrityChecker()

        drift = checker.find_signature_drift(source)
        unused = checker.find_unused_mocks(source)
        over = checker.detect_over_mocking(source)

        lines: list[str] = [
            "Mock Integrity Report",
            "=" * 50,
        ]

        if drift:
            lines.append(f"\nSignature drift ({len(drift)} found):")
            for item in drift:
                lines.append(
                    f"  Line {item['line']}: '{item['mock_target']}' — {item['issue']}"
                )
        else:
            lines.append("\nNo signature drift detected.")

        if unused:
            lines.append(f"\nUnused mocks ({len(unused)} found):")
            for item in unused:
                lines.append(
                    f"  Line {item['line']}: '{item['mock_name']}' — {item['suggestion']}"
                )
        else:
            lines.append("No unused mocks detected.")

        if over:
            lines.append(f"\nOver-mocked tests ({len(over)} found):")
            for item in over:
                lines.append(
                    f"  Line {item['line']}: '{item['test_name']}' uses "
                    f"{item['mock_count']} mocks — {item['suggestion']}"
                )
        else:
            lines.append("No over-mocked tests detected.")

        total = len(drift) + len(unused) + len(over)
        lines.append(f"\nTotal issues: {total}")
        return "\n".join(lines)

    registry.register_async(
        "mock-check",
        "Check mock signature drift, unused mocks, and over-mocking in test code",
        mock_check_handler,
    )

    # ------------------------------------------------------------------
    # /test-order — Analyze test execution order dependence
    # ------------------------------------------------------------------
    async def test_order_handler(args: str) -> str:
        """
        Usage: /test-order <json-object>
               /test-order --help

        JSON format:
          {
            "test_results": [{"name": str, "order_index": int, "passed": bool}, ...],
            "source": "<optional python source for dependency analysis>"
          }
        """
        from lidco.stability.test_order import TestOrderAnalyzer

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /test-order <json-object>\n"
                "\n"
                "JSON fields:\n"
                '  "test_results" — list of {name, order_index, passed}\n'
                '  "source"       — optional Python source for dependency analysis\n'
                "\n"
                "Detects order-dependent tests and inter-test dependencies."
            )

        try:
            data = json.loads(args.strip())
        except json.JSONDecodeError as exc:
            return f"Error parsing JSON: {exc}"

        if not isinstance(data, dict):
            return "Error: expected a JSON object."

        analyzer = TestOrderAnalyzer()
        test_results: list[dict] = data.get("test_results", [])
        source: str = data.get("source", "")

        lines: list[str] = [
            "Test Order Analysis Report",
            "=" * 50,
        ]

        if test_results:
            order_deps = analyzer.detect_order_dependence(test_results)
            if order_deps:
                lines.append(f"\nOrder-dependent tests ({len(order_deps)} found):")
                for item in order_deps:
                    lines.append(
                        f"  '{item['test_name']}': {item['issue']}\n"
                        f"    Evidence: {item['evidence']}"
                    )
            else:
                lines.append("\nNo order-dependent tests detected.")
            suggestions = analyzer.suggest_fixes(order_deps)
            if suggestions and suggestions != ["No order-dependence issues detected."]:
                lines.append("\nSuggestions:")
                for s in suggestions:
                    lines.append(f"  - {s}")
        else:
            lines.append("\nNo test_results provided.")

        if source:
            deps = analyzer.analyze_dependencies(source)
            if deps:
                lines.append(f"\nInter-test dependencies ({len(deps)} found):")
                for item in deps:
                    lines.append(
                        f"  '{item['test_name']}' depends on "
                        f"'{item['depends_on']}' [{item['type']}]"
                    )
            else:
                lines.append("No inter-test dependencies found in source.")

        return "\n".join(lines)

    registry.register_async(
        "test-order",
        "Analyze test execution order dependence and inter-test dependencies",
        test_order_handler,
    )

    # ------------------------------------------------------------------
    # /perf-guard — Track and report test performance regressions
    # ------------------------------------------------------------------
    async def perf_guard_handler(args: str) -> str:
        """
        Usage: /perf-guard <json-object>
               /perf-guard --help

        JSON format:
          {
            "current_times":  {"test_name": seconds, ...},
            "previous_times": {"test_name": seconds, ...},  (optional)
            "slow_threshold": 5.0,                          (optional, default 5.0)
            "num_workers": 4                                (optional, default 4)
          }
        """
        from lidco.stability.perf_guard import PerformanceRegressionGuard

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /perf-guard <json-object>\n"
                "\n"
                "JSON fields:\n"
                '  "current_times"  — dict of test_name -> duration (seconds)\n'
                '  "previous_times" — optional dict for regression comparison\n'
                '  "slow_threshold" — seconds to flag slow tests (default 5.0)\n'
                '  "num_workers"    — workers for parallelization suggestion (default 4)'
            )

        try:
            data = json.loads(args.strip())
        except json.JSONDecodeError as exc:
            return f"Error parsing JSON: {exc}"

        if not isinstance(data, dict):
            return "Error: expected a JSON object."

        current_times: dict[str, float] = data.get("current_times", {})
        previous_times: dict[str, float] = data.get("previous_times", {})
        slow_threshold: float = float(data.get("slow_threshold", 5.0))
        num_workers: int = int(data.get("num_workers", 4))

        if not isinstance(current_times, dict):
            return "Error: 'current_times' must be a dict of test_name -> float."

        guard = PerformanceRegressionGuard(slow_threshold=slow_threshold)
        guard.track_times(current_times)

        slow = guard.flag_slow_tests()
        regressions = (
            guard.detect_regressions(previous_times, current_times)
            if previous_times
            else []
        )
        parallel = guard.suggest_parallelization(current_times, num_workers)

        lines: list[str] = [
            "Performance Guard Report",
            "=" * 50,
            f"Tests tracked: {len(current_times)}",
            f"Slow threshold: {slow_threshold}s",
        ]

        if slow:
            lines.append(f"\nSlow tests ({len(slow)} found):")
            for item in slow:
                lines.append(
                    f"  '{item['test_name']}': {item['duration']:.3f}s "
                    f"(over by {item['over_by']:.3f}s)"
                )
        else:
            lines.append("\nNo slow tests detected.")

        if previous_times:
            if regressions:
                lines.append(f"\nPerformance regressions ({len(regressions)} found):")
                for item in regressions:
                    lines.append(
                        f"  '{item['test_name']}': "
                        f"{item['previous']:.3f}s → {item['current']:.3f}s "
                        f"(+{item['increase_pct']:.1f}%)"
                    )
            else:
                lines.append("No performance regressions detected.")
        else:
            lines.append("No previous_times provided; skipping regression check.")

        lines.append(
            f"\nParallelization suggestion ({num_workers} workers):\n"
            f"  Estimated time: {parallel['estimated_time']:.3f}s  "
            f"Speedup: {parallel['speedup']:.2f}x"
        )
        for i, worker_tests in enumerate(parallel["workers"]):
            if worker_tests:
                lines.append(f"  Worker {i+1}: {', '.join(worker_tests)}")

        return "\n".join(lines)

    registry.register_async(
        "perf-guard",
        "Track test performance, flag slow tests, detect regressions, suggest parallelization",
        perf_guard_handler,
    )
