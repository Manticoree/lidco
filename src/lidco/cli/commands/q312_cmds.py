"""
Q312 CLI commands — /load-profile, /load-run, /load-report, /load-bottleneck

Registered via register_q312_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q312_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q312 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /load-profile — Define / inspect a load profile
    # ------------------------------------------------------------------
    async def load_profile_handler(args: str) -> str:
        """
        Usage: /load-profile [--type steady|ramp_up|spike|soak]
                              [--users N] [--duration N] [--url URL]
                              [--ramp-up N] [--spike-users N] [name]
        """
        from lidco.loadtest.profile import (
            LoadProfile,
            ProfileType,
            RequestPattern,
            create_ramp_profile,
            create_spike_profile,
            create_soak_profile,
            create_steady_profile,
        )

        parts = shlex.split(args) if args.strip() else []
        ptype = "steady"
        users = 10
        duration = 60
        url = "http://localhost:8080"
        ramp_up = 10
        spike_users = 50
        name = "default"

        i = 0
        while i < len(parts):
            if parts[i] == "--type" and i + 1 < len(parts):
                ptype = parts[i + 1]
                i += 2
            elif parts[i] == "--users" and i + 1 < len(parts):
                try:
                    users = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--duration" and i + 1 < len(parts):
                try:
                    duration = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--url" and i + 1 < len(parts):
                url = parts[i + 1]
                i += 2
            elif parts[i] == "--ramp-up" and i + 1 < len(parts):
                try:
                    ramp_up = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--spike-users" and i + 1 < len(parts):
                try:
                    spike_users = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                name = parts[i]
                i += 1

        if ptype == "ramp_up":
            profile = create_ramp_profile(name, url, users=users, duration=duration, ramp_up=ramp_up)
        elif ptype == "spike":
            profile = create_spike_profile(
                name, url, users=users, spike_users=spike_users,
                duration=duration, ramp_up=ramp_up,
            )
        elif ptype == "soak":
            profile = create_soak_profile(name, url, users=users, duration=duration)
        else:
            profile = create_steady_profile(name, url, users=users, duration=duration)

        errors = profile.validate()
        if errors:
            return f"Validation errors:\n" + "\n".join(f"  - {e}" for e in errors)

        return profile.summary()

    registry.register_async(
        "load-profile",
        "Define and inspect a load test profile",
        load_profile_handler,
    )

    # ------------------------------------------------------------------
    # /load-run — Execute a load test
    # ------------------------------------------------------------------
    async def load_run_handler(args: str) -> str:
        """
        Usage: /load-run [--users N] [--duration N] [--timeout N] [url]
        """
        from lidco.loadtest.profile import create_steady_profile
        from lidco.loadtest.runner import LoadRunner

        parts = shlex.split(args) if args.strip() else []
        users = 5
        duration = 10
        timeout = 30.0
        url = "http://localhost:8080"

        i = 0
        while i < len(parts):
            if parts[i] == "--users" and i + 1 < len(parts):
                try:
                    users = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--duration" and i + 1 < len(parts):
                try:
                    duration = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--timeout" and i + 1 < len(parts):
                try:
                    timeout = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                url = parts[i]
                i += 1

        profile = create_steady_profile("cli-run", url, users=users, duration=duration)
        runner = LoadRunner(request_timeout=timeout)
        result = await runner.run(profile)

        stats = result.stats
        return (
            f"Load test complete: {result.profile_name}\n"
            f"  Requests: {stats.total_requests} "
            f"({stats.successful} ok, {stats.failed} err, {stats.timeouts} timeout)\n"
            f"  Latency: avg={stats.avg_latency_ms:.1f}ms "
            f"min={stats.min_latency_ms:.1f}ms max={stats.max_latency_ms:.1f}ms\n"
            f"  Throughput: {stats.requests_per_second:.1f} req/s\n"
            f"  Duration: {stats.elapsed_seconds:.1f}s"
        )

    registry.register_async(
        "load-run",
        "Execute a load test with stub executor",
        load_run_handler,
    )

    # ------------------------------------------------------------------
    # /load-report — Generate performance report from last run
    # ------------------------------------------------------------------
    async def load_report_handler(args: str) -> str:
        """
        Usage: /load-report [--users N] [--duration N] [--threshold-ms N] [url]
        """
        from lidco.loadtest.profile import create_steady_profile
        from lidco.loadtest.report import ReportGenerator
        from lidco.loadtest.runner import LoadRunner

        parts = shlex.split(args) if args.strip() else []
        users = 5
        duration = 10
        threshold_ms = 0.0
        url = "http://localhost:8080"

        i = 0
        while i < len(parts):
            if parts[i] == "--users" and i + 1 < len(parts):
                try:
                    users = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--duration" and i + 1 < len(parts):
                try:
                    duration = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--threshold-ms" and i + 1 < len(parts):
                try:
                    threshold_ms = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                url = parts[i]
                i += 1

        profile = create_steady_profile("cli-report", url, users=users, duration=duration)
        runner = LoadRunner()
        result = await runner.run(profile)

        gen = ReportGenerator(latency_threshold_ms=threshold_ms)
        report = gen.generate(result)
        return report.to_text()

    registry.register_async(
        "load-report",
        "Run a load test and generate performance report",
        load_report_handler,
    )

    # ------------------------------------------------------------------
    # /load-bottleneck — Analyse bottlenecks from a load run
    # ------------------------------------------------------------------
    async def load_bottleneck_handler(args: str) -> str:
        """
        Usage: /load-bottleneck [--users N] [--duration N]
                                [--slow-ms N] [--error-threshold N] [url]
        """
        from lidco.loadtest.bottleneck import BottleneckFinder
        from lidco.loadtest.profile import create_steady_profile
        from lidco.loadtest.runner import LoadRunner

        parts = shlex.split(args) if args.strip() else []
        users = 5
        duration = 10
        slow_ms = 500.0
        error_threshold = 0.05
        url = "http://localhost:8080"

        i = 0
        while i < len(parts):
            if parts[i] == "--users" and i + 1 < len(parts):
                try:
                    users = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--duration" and i + 1 < len(parts):
                try:
                    duration = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--slow-ms" and i + 1 < len(parts):
                try:
                    slow_ms = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--error-threshold" and i + 1 < len(parts):
                try:
                    error_threshold = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                url = parts[i]
                i += 1

        profile = create_steady_profile("cli-bottleneck", url, users=users, duration=duration)
        runner = LoadRunner()
        result = await runner.run(profile)

        finder = BottleneckFinder(
            slow_threshold_ms=slow_ms,
            error_rate_threshold=error_threshold,
        )
        report = finder.analyze(result)
        return report.to_text()

    registry.register_async(
        "load-bottleneck",
        "Run a load test and identify bottlenecks",
        load_bottleneck_handler,
    )
