"""
Q311 CLI commands — /chaos-experiment, /inject-fault, /chaos-monitor, /resilience-score

Registered via register_q311_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q311_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q311 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /chaos-experiment — Create and run chaos experiments
    # ------------------------------------------------------------------
    async def chaos_experiment_handler(args: str) -> str:
        """
        Usage: /chaos-experiment <type> [--duration N] [--intensity N] [--scope S] [--target T]
        Types: network_delay, disk_full, service_down, cpu_spike, memory_pressure, custom
        """
        from lidco.chaos.experiments import (
            ChaosExperimentRunner,
            ExperimentConfig,
            ExperimentType,
        )

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /chaos-experiment <type> [--duration N] "
                "[--intensity N] [--scope S] [--target T]\n"
                "Types: network_delay, disk_full, service_down, "
                "cpu_spike, memory_pressure, custom"
            )

        type_str = parts[0]
        try:
            exp_type = ExperimentType(type_str)
        except ValueError:
            valid = ", ".join(t.value for t in ExperimentType)
            return f"Unknown experiment type: {type_str!r}. Valid: {valid}"

        duration = 30.0
        intensity = 0.5
        scope = "local"
        target = ""

        i = 1
        while i < len(parts):
            if parts[i] == "--duration" and i + 1 < len(parts):
                try:
                    duration = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--intensity" and i + 1 < len(parts):
                try:
                    intensity = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--scope" and i + 1 < len(parts):
                scope = parts[i + 1]
                i += 2
            elif parts[i] == "--target" and i + 1 < len(parts):
                target = parts[i + 1]
                i += 2
            else:
                i += 1

        try:
            config = ExperimentConfig(
                experiment_type=exp_type,
                duration_seconds=duration,
                intensity=intensity,
                scope=scope,
                target=target,
            )
        except ValueError as exc:
            return f"Invalid config: {exc}"

        runner = ChaosExperimentRunner()
        exp = runner.create_experiment(config)
        started = runner.start_experiment(exp.id)

        return (
            f"Chaos experiment created and started:\n"
            f"  ID: {started.id}\n"
            f"  Type: {exp_type.value}\n"
            f"  Duration: {duration}s\n"
            f"  Intensity: {intensity}\n"
            f"  Scope: {scope}\n"
            f"  Status: {started.status.value}"
        )

    registry.register_async(
        "chaos-experiment",
        "Create and run chaos experiments",
        chaos_experiment_handler,
    )

    # ------------------------------------------------------------------
    # /inject-fault — Inject faults into the system
    # ------------------------------------------------------------------
    async def inject_fault_handler(args: str) -> str:
        """
        Usage: /inject-fault <type> --target <target> [--duration N] [--probability N]
        Types: timeout, error_response, slow_response, connection_drop, exception, custom
        """
        from lidco.chaos.injector import FaultConfig, FaultInjector, FaultType

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /inject-fault <type> --target <target> "
                "[--duration N] [--probability N]\n"
                "Types: timeout, error_response, slow_response, "
                "connection_drop, exception, custom"
            )

        type_str = parts[0]
        try:
            fault_type = FaultType(type_str)
        except ValueError:
            valid = ", ".join(t.value for t in FaultType)
            return f"Unknown fault type: {type_str!r}. Valid: {valid}"

        target = ""
        duration = 10.0
        probability = 1.0

        i = 1
        while i < len(parts):
            if parts[i] == "--target" and i + 1 < len(parts):
                target = parts[i + 1]
                i += 2
            elif parts[i] == "--duration" and i + 1 < len(parts):
                try:
                    duration = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--probability" and i + 1 < len(parts):
                try:
                    probability = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        if not target:
            return "Error: --target is required."

        try:
            config = FaultConfig(
                fault_type=fault_type,
                target=target,
                duration_seconds=duration,
                probability=probability,
            )
        except ValueError as exc:
            return f"Invalid config: {exc}"

        injector = FaultInjector()
        fault = injector.inject(config)

        return (
            f"Fault injected:\n"
            f"  ID: {fault.id}\n"
            f"  Type: {fault_type.value}\n"
            f"  Target: {target}\n"
            f"  Duration: {duration}s\n"
            f"  Probability: {probability}\n"
            f"  Status: {fault.status.value}"
        )

    registry.register_async(
        "inject-fault",
        "Inject faults into the system",
        inject_fault_handler,
    )

    # ------------------------------------------------------------------
    # /chaos-monitor — Monitor system during chaos experiments
    # ------------------------------------------------------------------
    async def chaos_monitor_handler(args: str) -> str:
        """
        Usage: /chaos-monitor [--sla-target N]
        """
        from lidco.chaos.monitor import ChaosMonitor

        parts = shlex.split(args) if args.strip() else []
        sla_target = 0.999

        i = 0
        while i < len(parts):
            if parts[i] == "--sla-target" and i + 1 < len(parts):
                try:
                    sla_target = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        monitor = ChaosMonitor(sla_target=sla_target)
        summary = monitor.summary()

        return (
            f"Chaos Monitor Status:\n"
            f"  Health: {summary['health_status']}\n"
            f"  Total metrics: {summary['total_metrics']}\n"
            f"  Total errors: {summary['total_errors']}\n"
            f"  Recoveries: {summary['recoveries']}\n"
            f"  SLA target: {summary['sla_target']}\n"
            f"  Actual availability: {summary['actual_availability']}\n"
            f"  Within SLA: {summary['within_sla']}"
        )

    registry.register_async(
        "chaos-monitor",
        "Monitor system during chaos experiments",
        chaos_monitor_handler,
    )

    # ------------------------------------------------------------------
    # /resilience-score — Score system resilience
    # ------------------------------------------------------------------
    async def resilience_score_handler(args: str) -> str:
        """
        Usage: /resilience-score [--recovery-target N] [--error-tolerance N]
        """
        from lidco.chaos.resilience import ResilienceScorer

        parts = shlex.split(args) if args.strip() else []
        recovery_target = 30.0
        error_tolerance = 0.1

        i = 0
        while i < len(parts):
            if parts[i] == "--recovery-target" and i + 1 < len(parts):
                try:
                    recovery_target = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--error-tolerance" and i + 1 < len(parts):
                try:
                    error_tolerance = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        scorer = ResilienceScorer(
            recovery_target_seconds=recovery_target,
            error_tolerance=error_tolerance,
        )
        report = scorer.score([])

        lines = [
            f"Resilience Score: {report.overall_score} ({report.grade})",
            f"  Experiments: {report.experiment_count}",
            f"  Failure modes tested: {report.failure_modes_tested}",
            f"  Avg recovery: {report.avg_recovery_seconds}s",
        ]
        if report.recommendations:
            lines.append("  Recommendations:")
            for r in report.recommendations:
                lines.append(f"    - {r}")

        return "\n".join(lines)

    registry.register_async(
        "resilience-score",
        "Score system resilience",
        resilience_score_handler,
    )
