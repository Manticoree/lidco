"""
Q346 CLI commands — /startup-profile, /shutdown-check, /health-suite, /crash-report

Registered via register_q346_commands(registry).
"""
from __future__ import annotations

import json


def register_q346_commands(registry) -> None:
    """Register Q346 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /startup-profile
    # ------------------------------------------------------------------
    async def startup_profile_handler(args: str) -> str:
        """
        Usage: /startup-profile [module1 module2 ...]
               /startup-profile demo
               /startup-profile --help

        Profile import costs for a list of modules.
        """
        from lidco.stability.startup_profiler import StartupProfiler

        stripped = args.strip()
        if not stripped or stripped in ("--help", "-h"):
            return (
                "Usage: /startup-profile [module1 module2 ...]\n"
                "  Measure import time for each module and report cold-start cost.\n\n"
                "  /startup-profile demo   — run with a built-in module list\n"
                "  /startup-profile json re os   — profile specific modules"
            )

        profiler = StartupProfiler()

        if stripped == "demo":
            modules = ["json", "re", "os", "sys", "pathlib", "collections"]
        else:
            modules = stripped.split()

        results = profiler.profile_imports(modules)
        report = profiler.generate_report()

        lines: list[str] = [report, "", "Per-module results:"]
        for r in results:
            status = "ok" if r["success"] else f"FAILED ({r['error']})"
            lines.append(f"  {r['module']:40s} {r['time_ms']:8.2f} ms  [{status}]")
        return "\n".join(lines)

    registry.register_slash_command("startup-profile", startup_profile_handler)

    # ------------------------------------------------------------------
    # /shutdown-check
    # ------------------------------------------------------------------
    async def shutdown_check_handler(args: str) -> str:
        """
        Usage: /shutdown-check demo
               /shutdown-check --help

        Simulate a graceful shutdown sequence and show results.
        """
        from lidco.stability.shutdown import ShutdownOrchestrator

        stripped = args.strip()
        if not stripped or stripped in ("--help", "-h"):
            return (
                "Usage: /shutdown-check demo\n"
                "  Simulate a shutdown sequence with demo handlers and report results."
            )

        orchestrator = ShutdownOrchestrator(timeout=5.0)

        if stripped == "demo":
            orchestrator.register_handler("flush_logs", lambda: None, priority=10)
            orchestrator.register_handler("close_connections", lambda: None, priority=5)
            orchestrator.register_handler("save_cache", lambda: None, priority=1)

            result = orchestrator.execute_shutdown()
            lines: list[str] = [
                f"Shutdown {'succeeded' if result['success'] else 'had failures'}",
                f"  Total time  : {result['total_time_ms']:.2f} ms",
                f"  Executed    : {', '.join(result['executed']) or '(none)'}",
            ]
            if result["failed"]:
                for f in result["failed"]:
                    lines.append(f"  FAILED      : {f['name']} — {f['error']}")
            return "\n".join(lines)

        return "Unknown argument. Use '/shutdown-check demo' or '/shutdown-check --help'."

    registry.register_slash_command("shutdown-check", shutdown_check_handler)

    # ------------------------------------------------------------------
    # /health-suite
    # ------------------------------------------------------------------
    async def health_suite_handler(args: str) -> str:
        """
        Usage: /health-suite [path]
               /health-suite demo
               /health-suite --help

        Run all health checks and display aggregated results.
        """
        from lidco.stability.health_suite import HealthCheckSuite

        stripped = args.strip()
        if stripped in ("--help", "-h"):
            return (
                "Usage: /health-suite [path]\n"
                "  Run disk, memory, and config health checks.\n\n"
                "  /health-suite          — check current directory\n"
                "  /health-suite /tmp     — check a specific path\n"
                "  /health-suite demo     — run with demo config"
            )

        suite = HealthCheckSuite()
        path = "." if stripped in ("", "demo") else stripped
        config = {"model": "gpt-4", "timeout": 30} if stripped == "demo" else {}

        report = suite.run_all(path=path, config=config)
        overall = "HEALTHY" if report["overall_healthy"] else "UNHEALTHY"

        lines: list[str] = [
            f"Health Suite: {overall}",
            f"Timestamp: {report['timestamp']}",
            "",
        ]
        for check_name, result in report["checks"].items():
            healthy_key = "healthy" if "healthy" in result else "valid"
            status = "ok" if result.get(healthy_key) else "FAIL"
            lines.append(f"  [{status}] {check_name}")
            for key, val in result.items():
                if key != healthy_key:
                    lines.append(f"        {key}: {val}")
        return "\n".join(lines)

    registry.register_slash_command("health-suite", health_suite_handler)

    # ------------------------------------------------------------------
    # /crash-report
    # ------------------------------------------------------------------
    async def crash_report_handler(args: str) -> str:
        """
        Usage: /crash-report demo
               /crash-report repro
               /crash-report --help

        Generate a crash report or show reproducibility information.
        """
        from lidco.stability.crash_reporter import CrashReporter

        stripped = args.strip()
        if not stripped or stripped in ("--help", "-h"):
            return (
                "Usage: /crash-report demo   — generate a sample crash report\n"
                "       /crash-report repro  — show reproducibility information\n"
                "       /crash-report --help — show this help"
            )

        reporter = CrashReporter()

        if stripped == "demo":
            try:
                raise ValueError("Demo crash: intentional test exception")
            except ValueError as exc:
                context = reporter.capture_context(exc)
            return reporter.format_report(context)

        if stripped == "repro":
            info = reporter.get_reproducibility_info()
            lines: list[str] = [
                "=== Reproducibility Info ===",
                f"Python  : {info['python_version']}",
                f"Platform: {info['platform']}",
                f"CWD     : {info['cwd']}",
                f"Env vars: {len(info['env_vars'])} safe variables collected",
            ]
            return "\n".join(lines)

        return "Unknown argument. Use '/crash-report demo', '/crash-report repro', or '--help'."

    registry.register_slash_command("crash-report", crash_report_handler)
