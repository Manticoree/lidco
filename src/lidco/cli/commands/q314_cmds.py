"""
Q314 CLI commands — /flaky-detect, /flaky-analyze, /flaky-quarantine, /flaky-dashboard

Registered via register_q314_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q314_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q314 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /flaky-detect — Detect flaky tests from history
    # ------------------------------------------------------------------
    async def flaky_detect_handler(args: str) -> str:
        """
        Usage: /flaky-detect [--min-runs N] [--threshold F] [path]
        """
        from lidco.flaky.detector import FlakyDetector, TestRun

        parts = shlex.split(args) if args.strip() else []
        min_runs = 3
        threshold = 0.95
        path = "."

        i = 0
        while i < len(parts):
            if parts[i] == "--min-runs" and i + 1 < len(parts):
                try:
                    min_runs = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--threshold" and i + 1 < len(parts):
                try:
                    threshold = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                path = parts[i]
                i += 1

        detector = FlakyDetector(min_runs=min_runs, flaky_threshold=threshold)
        # In real usage, runs would be loaded from test history files
        report = detector.detect([])

        lines = [
            f"Flaky Detection (min_runs={min_runs}, threshold={threshold}):",
            f"  Total tests: {report.total_tests}",
            f"  Flaky tests: {report.flaky_count}",
            f"  Flaky rate: {report.flaky_rate:.1%}",
        ]
        for r in report.results:
            if r.is_flaky:
                lines.append(
                    f"  FLAKY: {r.test_name} — "
                    f"pass_rate={r.pass_rate:.1%}, "
                    f"severity={r.severity.value}"
                )
        return "\n".join(lines)

    registry.register_async(
        "flaky-detect",
        "Detect flaky tests from test history",
        flaky_detect_handler,
    )

    # ------------------------------------------------------------------
    # /flaky-analyze — Analyze flaky root causes
    # ------------------------------------------------------------------
    async def flaky_analyze_handler(args: str) -> str:
        """
        Usage: /flaky-analyze [--min-runs N] [--timing-threshold F]
        """
        from lidco.flaky.analyzer import FlakyAnalyzer

        parts = shlex.split(args) if args.strip() else []
        min_runs = 3
        timing_threshold = 500.0

        i = 0
        while i < len(parts):
            if parts[i] == "--min-runs" and i + 1 < len(parts):
                try:
                    min_runs = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--timing-threshold" and i + 1 < len(parts):
                try:
                    timing_threshold = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        analyzer = FlakyAnalyzer(
            min_runs=min_runs, timing_threshold_ms=timing_threshold
        )
        report = analyzer.analyze([])

        lines = [
            f"Flaky Analysis (min_runs={min_runs}):",
            f"  Analyzed: {report.total_analyzed}",
        ]
        for r in report.results:
            lines.append(
                f"  {r.test_name}: cause={r.primary_cause.value}, "
                f"recommendation={r.recommendation}"
            )
        if report.cause_counts:
            lines.append("  Cause summary:")
            for cause, count in sorted(report.cause_counts.items()):
                lines.append(f"    {cause}: {count}")
        return "\n".join(lines)

    registry.register_async(
        "flaky-analyze",
        "Analyze flaky test root causes",
        flaky_analyze_handler,
    )

    # ------------------------------------------------------------------
    # /flaky-quarantine — Manage flaky test quarantine
    # ------------------------------------------------------------------
    async def flaky_quarantine_handler(args: str) -> str:
        """
        Usage: /flaky-quarantine [add|release|override|status] [test_name] [--reason TEXT]
        """
        from lidco.flaky.quarantine import FlakyQuarantine

        parts = shlex.split(args) if args.strip() else []
        action = "status"
        test_name = ""
        reason = ""

        i = 0
        while i < len(parts):
            if parts[i] == "--reason" and i + 1 < len(parts):
                reason = parts[i + 1]
                i += 2
            elif not test_name and parts[i] in ("add", "release", "override", "status"):
                action = parts[i]
                i += 1
            elif not test_name:
                test_name = parts[i]
                i += 1
            else:
                i += 1

        quarantine = FlakyQuarantine()

        if action == "add" and test_name:
            entry = quarantine.quarantine(test_name, reason=reason)
            return f"Quarantined: {entry.test_name} (reason={entry.reason})"
        elif action == "release" and test_name:
            entry = quarantine.release(test_name)
            if entry is None:
                return f"Test not found in quarantine: {test_name}"
            return f"Released: {entry.test_name}"
        elif action == "override" and test_name:
            entry = quarantine.override(test_name)
            if entry is None:
                return f"Test not found in quarantine: {test_name}"
            return f"Overridden: {entry.test_name}"
        else:
            s = quarantine.summary()
            return (
                f"Quarantine Status:\n"
                f"  Total: {s.total}\n"
                f"  Active: {s.active}\n"
                f"  Released: {s.released}\n"
                f"  Expired: {s.expired}\n"
                f"  Overridden: {s.overridden}"
            )

    registry.register_async(
        "flaky-quarantine",
        "Manage flaky test quarantine",
        flaky_quarantine_handler,
    )

    # ------------------------------------------------------------------
    # /flaky-dashboard — Flaky test dashboard
    # ------------------------------------------------------------------
    async def flaky_dashboard_handler(args: str) -> str:
        """
        Usage: /flaky-dashboard [--top N]
        """
        from lidco.flaky.dashboard import FlakyDashboard

        parts = shlex.split(args) if args.strip() else []
        top_n = 10

        i = 0
        while i < len(parts):
            if parts[i] == "--top" and i + 1 < len(parts):
                try:
                    top_n = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        dashboard = FlakyDashboard()
        report = dashboard.generate([], top_n=top_n)
        return dashboard.format_text(report)

    registry.register_async(
        "flaky-dashboard",
        "Flaky test dashboard with metrics",
        flaky_dashboard_handler,
    )
