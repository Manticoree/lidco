"""Q129 CLI commands: /metrics, /health."""
from __future__ import annotations

_state: dict = {}


def register(registry) -> None:
    """Register Q129 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def metrics_handler(args: str) -> str:
        from lidco.telemetry.metrics_store import MetricsStore

        if "store" not in _state:
            _state["store"] = MetricsStore()
        store: MetricsStore = _state["store"]

        parts = args.strip().split(maxsplit=3)
        sub = parts[0].lower() if parts else ""

        if sub == "record":
            if len(parts) < 3:
                return "Usage: /metrics record <name> <value>"
            name = parts[1]
            try:
                value = float(parts[2])
            except ValueError:
                return "Value must be a number."
            pt = store.record(name, value)
            return f"Recorded {name}={pt.value}"

        if sub == "show":
            if len(parts) < 2:
                names = store.names()
                if not names:
                    return "No metrics recorded."
                lines = ["Metrics:"]
                for n in names:
                    last = store.last(n)
                    lines.append(f"  {n}: last={last.value if last else 'N/A'}, count={len(store.get_series(n))}")
                return "\n".join(lines)
            name = parts[1]
            series = store.get_series(name)
            if not series:
                return f"No data for '{name}'."
            lines = [f"Series '{name}' ({len(series)} points):"]
            for pt in series[-5:]:
                lines.append(f"  {pt.value}")
            return "\n".join(lines)

        if sub == "agg":
            if len(parts) < 3:
                return "Usage: /metrics agg <name> <fn>"
            name = parts[1]
            fn = parts[2]
            try:
                result = store.aggregate(name, fn)
                return f"{fn}({name}) = {result}"
            except ValueError as exc:
                return str(exc)

        if sub == "clear":
            name = parts[1] if len(parts) > 1 else None
            store.clear(name)
            return f"Cleared {'all metrics' if name is None else repr(name)}."

        return (
            "Usage: /metrics <sub>\n"
            "  record <name> <value>   -- record a metric point\n"
            "  show [name]             -- show metrics\n"
            "  agg <name> <fn>         -- aggregate (avg/sum/min/max/count/last)\n"
            "  clear [name]            -- clear metrics"
        )

    async def health_handler(args: str) -> str:
        from lidco.telemetry.health_check import HealthCheck, HealthRegistry

        if "health_reg" not in _state:
            _state["health_reg"] = HealthRegistry()
        reg: HealthRegistry = _state["health_reg"]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "check":
            statuses = reg.run_all()
            if not statuses:
                return "No health checks registered."
            lines = ["Health checks:"]
            for s in statuses:
                icon = "OK" if s.healthy else "FAIL"
                lines.append(f"  [{icon}] {s.name}: {s.message}")
            return "\n".join(lines)

        if sub == "status":
            summary = reg.summary()
            overall = "healthy" if reg.is_healthy() else "unhealthy"
            return (
                f"Overall: {overall} | "
                f"healthy={summary['healthy']} unhealthy={summary['unhealthy']}"
            )

        return (
            "Usage: /health <sub>\n"
            "  check    -- run all health checks\n"
            "  status   -- summary status"
        )

    registry.register(SlashCommand("metrics", "Record and query metrics", metrics_handler))
    registry.register(SlashCommand("health", "Run health checks", health_handler))
