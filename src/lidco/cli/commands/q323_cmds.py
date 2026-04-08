"""
Q323 CLI commands — /service-map, /traffic-analyze, /circuit-config, /rate-config

Registered via register_q323_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q323_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q323 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /service-map — Discover services and show dependency map
    # ------------------------------------------------------------------
    async def service_map_handler(args: str) -> str:
        """
        Usage: /service-map [--json] [--unhealthy]
        """
        from lidco.mesh.mapper import ServiceMapper

        parts = shlex.split(args) if args.strip() else []
        show_json = "--json" in parts
        show_unhealthy = "--unhealthy" in parts

        mapper = ServiceMapper()
        dep_map = mapper.dependency_map()

        if not dep_map.services:
            return "No services discovered."

        if show_unhealthy:
            unhealthy = mapper.unhealthy_services()
            if not unhealthy:
                return "All services are healthy."
            lines = ["Unhealthy services:"]
            for svc in unhealthy:
                lines.append(f"  {svc.name} v{svc.version}: {svc.health.value}")
            return "\n".join(lines)

        lines = [f"Service Map: {len(dep_map.services)} services, {len(dep_map.edges)} edges"]
        for svc in dep_map.services:
            deps = mapper.dependencies_of(svc.name)
            dep_str = f" -> {', '.join(deps)}" if deps else ""
            lines.append(f"  {svc.name} v{svc.version} [{svc.health.value}]{dep_str}")

        version_matrix = mapper.version_matrix()
        if version_matrix.entries:
            lines.append("")
            lines.append("Version matrix:")
            for entry in version_matrix.entries:
                lines.append(f"  {entry.service}: {entry.version} ({entry.instances} instances)")

        return "\n".join(lines)

    registry.register_async(
        "service-map",
        "Discover services and show dependency map",
        service_map_handler,
    )

    # ------------------------------------------------------------------
    # /traffic-analyze — Analyze service-to-service traffic
    # ------------------------------------------------------------------
    async def traffic_analyze_handler(args: str) -> str:
        """
        Usage: /traffic-analyze [--top N]
        """
        from lidco.mesh.traffic import TrafficAnalyzer

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

        analyzer = TrafficAnalyzer()
        report = analyzer.analyze()

        if not report.pairs:
            return "No traffic data available."

        lines = [f"Traffic Analysis: {report.total_records} records"]
        for p in report.pairs[:top_n]:
            lines.append(
                f"  {p.source} -> {p.target}: "
                f"{p.total_requests} reqs, "
                f"avg={p.avg_latency_ms}ms, "
                f"p99={p.p99_latency_ms}ms, "
                f"err={p.error_rate:.1%}, "
                f"pattern={p.pattern.value}"
            )

        if report.hotspots:
            lines.append("")
            lines.append("Hotspots:")
            for h in report.hotspots:
                lines.append(f"  - {h}")

        return "\n".join(lines)

    registry.register_async(
        "traffic-analyze",
        "Analyze service-to-service traffic",
        traffic_analyze_handler,
    )

    # ------------------------------------------------------------------
    # /circuit-config — Generate circuit breaker configurations
    # ------------------------------------------------------------------
    async def circuit_config_handler(args: str) -> str:
        """
        Usage: /circuit-config [--service NAME]
        """
        from lidco.mesh.circuit_config import CircuitConfigGenerator

        parts = shlex.split(args) if args.strip() else []
        service_filter: str | None = None

        i = 0
        while i < len(parts):
            if parts[i] == "--service" and i + 1 < len(parts):
                service_filter = parts[i + 1]
                i += 2
            else:
                i += 1

        gen = CircuitConfigGenerator()

        if service_filter:
            cfg = gen.generate_for_service(service_filter)
            return (
                f"Circuit Breaker Config for {cfg.service}:\n"
                f"  Failure threshold: {cfg.failure_threshold}\n"
                f"  Recovery timeout: {cfg.recovery_timeout_s}s\n"
                f"  Half-open max calls: {cfg.half_open_max_calls}\n"
                f"  Window size: {cfg.window_size_s}s\n"
                f"  Error rate threshold: {cfg.error_rate_threshold}\n"
                f"  Slow call duration: {cfg.slow_call_duration_ms}ms\n"
                f"  Slow call rate threshold: {cfg.slow_call_rate_threshold}"
            )

        report = gen.generate()
        if not report.configs:
            return "No failure data available for circuit config generation."

        lines = [f"Circuit Breaker Configs: {len(report.configs)} services"]
        for cfg in report.configs:
            lines.append(
                f"  {cfg.service}: threshold={cfg.failure_threshold}, "
                f"recovery={cfg.recovery_timeout_s}s, "
                f"err_rate={cfg.error_rate_threshold}"
            )

        if report.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for r in report.recommendations:
                lines.append(f"  - {r}")

        return "\n".join(lines)

    registry.register_async(
        "circuit-config",
        "Generate circuit breaker configurations",
        circuit_config_handler,
    )

    # ------------------------------------------------------------------
    # /rate-config — Generate rate limit configurations
    # ------------------------------------------------------------------
    async def rate_config_handler(args: str) -> str:
        """
        Usage: /rate-config [--margin FLOAT] [--burst FLOAT]
        """
        from lidco.mesh.rate_limits import RateLimitGenerator

        parts = shlex.split(args) if args.strip() else []
        margin = 0.8
        burst = 2.0

        i = 0
        while i < len(parts):
            if parts[i] == "--margin" and i + 1 < len(parts):
                try:
                    margin = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--burst" and i + 1 < len(parts):
                try:
                    burst = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        gen = RateLimitGenerator(safety_margin=margin)
        gen.set_burst_multiplier(burst)
        report = gen.generate()

        if not report.configs:
            return "No capacity data available for rate limit generation."

        lines = [f"Rate Limit Configs: {report.total_endpoints} endpoints"]
        for cfg in report.configs:
            lines.append(
                f"  {cfg.service}/{cfg.endpoint}: "
                f"{cfg.requests_per_second} rps, "
                f"burst={cfg.burst_size}, "
                f"priority={cfg.priority.value}, "
                f"retry_after={cfg.retry_after_s}s"
            )

        if report.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for r in report.recommendations:
                lines.append(f"  - {r}")

        return "\n".join(lines)

    registry.register_async(
        "rate-config",
        "Generate rate limit configurations",
        rate_config_handler,
    )
