"""Q297 CLI commands: /metrics, /analyze-logs, /traces, /alerts."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q297 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /metrics
    # ------------------------------------------------------------------

    async def metrics_handler(args: str) -> str:
        from lidco.observability.exporter import MetricsExporter

        if "exporter" not in _state:
            _state["exporter"] = MetricsExporter()

        exp: MetricsExporter = _state["exporter"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "record":
            # /metrics record <name> <value>
            if len(parts) < 3:
                return "Usage: /metrics record <name> <value>"
            name = parts[1]
            try:
                value = float(parts[2])
            except ValueError:
                return f"Invalid value: {parts[2]}"
            exp.record(name, value)
            return f"Recorded {name}={value}"

        if sub == "counter":
            name = parts[1] if len(parts) > 1 else ""
            if not name:
                return "Usage: /metrics counter <name>"
            val = exp.counter(name)
            return f"{name} = {val}"

        if sub == "histogram":
            if len(parts) < 3:
                return "Usage: /metrics histogram <name> <value>"
            name = parts[1]
            try:
                value = float(parts[2])
            except ValueError:
                return f"Invalid value: {parts[2]}"
            exp.histogram(name, value)
            return f"Histogram {name} += {value}"

        if sub == "export":
            fmt = parts[1].lower() if len(parts) > 1 else "json"
            if fmt == "prometheus":
                return exp.export_prometheus() or "(empty)"
            return json.dumps(exp.export_json(), indent=2)

        if sub == "summary":
            return json.dumps(exp.summary(), indent=2)

        return (
            "Usage: /metrics <subcommand>\n"
            "  record <name> <value>      -- record a metric point\n"
            "  counter <name>             -- increment counter\n"
            "  histogram <name> <value>   -- add to histogram\n"
            "  export [json|prometheus]   -- export metrics\n"
            "  summary                    -- show summary"
        )

    # ------------------------------------------------------------------
    # /analyze-logs
    # ------------------------------------------------------------------

    async def analyze_logs_handler(args: str) -> str:
        from lidco.observability.log_analyzer import LogAnalyzer2

        if "analyzer" not in _state:
            _state["analyzer"] = LogAnalyzer2()

        analyzer: LogAnalyzer2 = _state["analyzer"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "ingest":
            if not rest:
                return "Usage: /analyze-logs ingest <lines...>"
            lines = rest.split("\\n")
            count = analyzer.ingest(lines)
            return f"Ingested {count} line(s)."

        if sub == "patterns":
            pats = analyzer.detect_patterns()
            if not pats:
                return "No patterns detected."
            lines_out = [f"{len(pats)} pattern(s):"]
            for p in pats:
                lines_out.append(f"  [{p.severity}] {p.pattern}: {p.count}")
            return "\n".join(lines_out)

        if sub == "clusters":
            clusters = analyzer.cluster_errors()
            if not clusters:
                return "No error clusters."
            lines_out = [f"{len(clusters)} cluster(s):"]
            for c in clusters:
                lines_out.append(f"  {c.key[:60]}... ({c.count})")
            return "\n".join(lines_out)

        if sub == "root-cause":
            if not rest:
                return "Usage: /analyze-logs root-cause <error message>"
            return analyzer.suggest_root_cause(rest)

        if sub == "summary":
            return json.dumps(analyzer.summary(), indent=2)

        return (
            "Usage: /analyze-logs <subcommand>\n"
            "  ingest <lines>         -- ingest log lines (\\n separated)\n"
            "  patterns               -- detect log patterns\n"
            "  clusters               -- cluster error lines\n"
            "  root-cause <error>     -- suggest root cause\n"
            "  summary                -- show summary"
        )

    # ------------------------------------------------------------------
    # /traces
    # ------------------------------------------------------------------

    async def traces_handler(args: str) -> str:
        from lidco.observability.traces import TraceCollector

        if "collector" not in _state:
            _state["collector"] = TraceCollector()

        collector: TraceCollector = _state["collector"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "start":
            name = parts[1] if len(parts) > 1 else ""
            parent = parts[2] if len(parts) > 2 else None
            if not name:
                return "Usage: /traces start <name> [parent_span_id]"
            span = collector.start_span(name, parent)
            return f"Started span {span.span_id} (trace={span.trace_id})"

        if sub == "end":
            span_id = parts[1] if len(parts) > 1 else ""
            if not span_id:
                return "Usage: /traces end <span_id>"
            try:
                span = collector.end_span(span_id)
            except KeyError:
                return f"Span '{span_id}' not found."
            return f"Ended span {span.span_id} ({span.duration_ms:.1f}ms)"

        if sub == "get":
            trace_id = parts[1] if len(parts) > 1 else ""
            if not trace_id:
                return "Usage: /traces get <trace_id>"
            spans = collector.get_trace(trace_id)
            if not spans:
                return f"No spans for trace '{trace_id}'."
            lines_out = [f"Trace {trace_id} ({len(spans)} span(s)):"]
            for s in spans:
                lines_out.append(f"  {s.name} [{s.span_id}] {s.duration_ms:.1f}ms")
            return "\n".join(lines_out)

        if sub == "latency":
            trace_id = parts[1] if len(parts) > 1 else ""
            if not trace_id:
                return "Usage: /traces latency <trace_id>"
            breakdown = collector.latency_breakdown(trace_id)
            if not breakdown:
                return f"No latency data for trace '{trace_id}'."
            return json.dumps(breakdown, indent=2)

        if sub == "map":
            smap = collector.service_map()
            if not smap:
                return "No service map data."
            return json.dumps(smap, indent=2)

        return (
            "Usage: /traces <subcommand>\n"
            "  start <name> [parent]  -- start a span\n"
            "  end <span_id>          -- end a span\n"
            "  get <trace_id>         -- show trace spans\n"
            "  latency <trace_id>     -- latency breakdown\n"
            "  map                    -- service map"
        )

    # ------------------------------------------------------------------
    # /alerts
    # ------------------------------------------------------------------

    async def alerts_handler(args: str) -> str:
        from lidco.observability.alerts import AlertManager2, AlertSeverity

        if "alert_mgr" not in _state:
            _state["alert_mgr"] = AlertManager2()

        mgr: AlertManager2 = _state["alert_mgr"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=3)
        sub = parts[0].lower() if parts else ""

        if sub == "add":
            # /alerts add <name> <condition> <threshold>
            if len(parts) < 4:
                return "Usage: /alerts add <name> <condition> <threshold>"
            name = parts[1]
            cond = parts[2]
            try:
                thresh = float(parts[3])
            except ValueError:
                return f"Invalid threshold: {parts[3]}"
            rule = mgr.add_rule(name, cond, thresh, metric_name=name)
            return f"Rule '{rule.name}' created (id={rule.rule_id})"

        if sub == "evaluate":
            # /alerts evaluate <metric_name> <value>
            if len(parts) < 3:
                return "Usage: /alerts evaluate <metric_name> <value>"
            metric = parts[1]
            try:
                val = float(parts[2])
            except ValueError:
                return f"Invalid value: {parts[2]}"
            fired = mgr.evaluate(metric, val)
            if not fired:
                return "No alerts fired."
            lines = [f"{len(fired)} alert(s) fired:"]
            for a in fired:
                lines.append(f"  [{a.severity}] {a.rule_name}: {a.value} {a.threshold}")
            return "\n".join(lines)

        if sub == "silence":
            if len(parts) < 3:
                return "Usage: /alerts silence <rule_id> <seconds>"
            rule_id = parts[1]
            try:
                dur = float(parts[2])
            except ValueError:
                return f"Invalid duration: {parts[2]}"
            try:
                mgr.silence(rule_id, dur)
            except KeyError:
                return f"Rule '{rule_id}' not found."
            return f"Silenced rule {rule_id} for {dur}s."

        if sub == "active":
            alerts = mgr.active_alerts()
            if not alerts:
                return "No active alerts."
            lines = [f"{len(alerts)} active alert(s):"]
            for a in alerts:
                lines.append(f"  [{a.severity}] {a.rule_name} ({a.alert_id})")
            return "\n".join(lines)

        if sub == "escalate":
            aid = parts[1] if len(parts) > 1 else ""
            if not aid:
                return "Usage: /alerts escalate <alert_id>"
            ok = mgr.escalate(aid)
            return f"Escalated {aid}." if ok else f"Alert '{aid}' not found."

        return (
            "Usage: /alerts <subcommand>\n"
            "  add <name> <cond> <thresh>  -- add an alert rule\n"
            "  evaluate <metric> <value>   -- evaluate rules\n"
            "  silence <rule_id> <secs>    -- silence a rule\n"
            "  active                      -- list active alerts\n"
            "  escalate <alert_id>         -- escalate an alert"
        )

    registry.register(SlashCommand("metrics", "Export and manage metrics", metrics_handler))
    registry.register(SlashCommand("analyze-logs", "Analyze log patterns", analyze_logs_handler))
    registry.register(SlashCommand("traces", "Distributed tracing", traces_handler))
    registry.register(SlashCommand("alerts", "Alert rules management", alerts_handler))
