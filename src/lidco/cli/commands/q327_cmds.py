"""Q327 CLI commands — /parse-log, /correlate-logs, /log-anomaly, /log-dashboard

Registered via register_q327_commands(registry).
"""

from __future__ import annotations

import json
import os
import shlex


def register_q327_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q327 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /parse-log — Parse log files
    # ------------------------------------------------------------------
    async def parse_log_handler(args: str) -> str:
        """
        Usage: /parse-log <file>
               /parse-log --text <inline-text>
               /parse-log --format json|syslog|custom <file>
        """
        from lidco.logintel.parser import LogParser

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /parse-log <subcommand>\n"
                "  <file>                        parse a log file\n"
                "  --text <inline-text>           parse inline text\n"
                "  --format <fmt> <file>          parse with explicit format"
            )

        parser = LogParser()

        if parts[0] == "--text":
            text = args.strip()[len("--text"):].strip()
            if not text:
                return "Usage: /parse-log --text <inline-text>"
            result = parser.parse(text)
            return (
                f"Parsed {result.parsed_lines}/{result.total_lines} lines\n"
                f"Format: {result.format_detected.value}\n"
                f"Entries: {len(result.entries)}"
            )

        if parts[0] == "--format":
            if len(parts) < 3:
                return "Usage: /parse-log --format <fmt> <file>"
            fmt_name = parts[1]
            filepath = parts[2]
            if not os.path.isfile(filepath):
                return f"File not found: {filepath}"
            with open(filepath, encoding="utf-8", errors="replace") as f:
                text = f.read()
            result = parser.parse(text)
            return (
                f"Parsed {result.parsed_lines}/{result.total_lines} lines\n"
                f"Format: {fmt_name}\n"
                f"Entries: {len(result.entries)}"
            )

        # Default: treat as file path
        filepath = parts[0]
        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"
        with open(filepath, encoding="utf-8", errors="replace") as f:
            text = f.read()
        result = parser.parse(text)
        lines = [
            f"Parsed {result.parsed_lines}/{result.total_lines} lines",
            f"Format: {result.format_detected.value}",
            f"Entries: {len(result.entries)}",
            f"Success rate: {result.success_rate:.0%}",
        ]
        if result.errors:
            lines.append(f"Errors: {len(result.errors)}")
        return "\n".join(lines)

    registry.register_async("parse-log", "Parse structured/unstructured log files", parse_log_handler)

    # ------------------------------------------------------------------
    # /correlate-logs — Correlate logs across services
    # ------------------------------------------------------------------
    async def correlate_logs_handler(args: str) -> str:
        """
        Usage: /correlate-logs <file> [--trace-field <field>]
               /correlate-logs timeline <file>
               /correlate-logs root-cause <file> <trace_id>
        """
        from lidco.logintel.correlator import LogCorrelator
        from lidco.logintel.parser import LogParser

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /correlate-logs <subcommand>\n"
                "  <file>                               correlate entries\n"
                "  timeline <file>                      build timeline\n"
                "  root-cause <file> <trace_id>         find root cause"
            )

        trace_field = "trace_id"
        # Check for --trace-field flag
        if "--trace-field" in parts:
            idx = parts.index("--trace-field")
            if idx + 1 < len(parts):
                trace_field = parts[idx + 1]
                parts = parts[:idx] + parts[idx + 2:]

        subcmd = parts[0].lower() if parts else ""

        if subcmd == "timeline":
            if len(parts) < 2:
                return "Usage: /correlate-logs timeline <file>"
            filepath = parts[1]
            if not os.path.isfile(filepath):
                return f"File not found: {filepath}"
            with open(filepath, encoding="utf-8", errors="replace") as f:
                text = f.read()
            parser = LogParser()
            parsed = parser.parse(text)
            correlator = LogCorrelator(trace_field=trace_field)
            correlator.add_entries(parsed.entries)
            events = correlator.build_timeline()
            lines = [f"Timeline ({len(events)} events):"]
            for ev in events[:20]:
                lines.append(f"  {ev.timestamp} [{ev.service}] {ev.level}: {ev.message[:80]}")
            if len(events) > 20:
                lines.append(f"  ... and {len(events) - 20} more")
            return "\n".join(lines)

        if subcmd == "root-cause":
            if len(parts) < 3:
                return "Usage: /correlate-logs root-cause <file> <trace_id>"
            filepath = parts[1]
            tid = parts[2]
            if not os.path.isfile(filepath):
                return f"File not found: {filepath}"
            with open(filepath, encoding="utf-8", errors="replace") as f:
                text = f.read()
            parser = LogParser()
            parsed = parser.parse(text)
            correlator = LogCorrelator(trace_field=trace_field)
            correlator.add_entries(parsed.entries)
            chain = correlator.find_root_cause(tid)
            if chain is None:
                return f"No root cause found for trace '{tid}'"
            return (
                f"Root cause for trace '{tid}':\n"
                f"  Error: {chain.root_cause[:120]}\n"
                f"  Chain depth: {chain.depth}"
            )

        # Default: correlate file
        filepath = parts[0]
        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"
        with open(filepath, encoding="utf-8", errors="replace") as f:
            text = f.read()
        parser = LogParser()
        parsed = parser.parse(text)
        correlator = LogCorrelator(trace_field=trace_field)
        correlator.add_entries(parsed.entries)
        traces = correlator.correlate()
        svc_map = correlator.service_map()
        lines = [
            f"Entries: {correlator.entry_count}",
            f"Traces: {len(traces)}",
            f"Services: {', '.join(svc_map.keys()) if svc_map else 'none'}",
        ]
        for t in traces[:10]:
            status = "ERROR" if t.has_error else "OK"
            lines.append(f"  {t.trace_id}: {t.entry_count} entries, services={t.services} [{status}]")
        return "\n".join(lines)

    registry.register_async("correlate-logs", "Correlate logs across services", correlate_logs_handler)

    # ------------------------------------------------------------------
    # /log-anomaly — Detect log anomalies
    # ------------------------------------------------------------------
    async def log_anomaly_handler(args: str) -> str:
        """
        Usage: /log-anomaly <file>
               /log-anomaly --baseline <baseline-file> <file>
        """
        from lidco.logintel.anomaly import LogAnomalyDetector
        from lidco.logintel.parser import LogParser

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /log-anomaly <subcommand>\n"
                "  <file>                                detect anomalies\n"
                "  --baseline <baseline-file> <file>     use baseline for comparison"
            )

        detector = LogAnomalyDetector()
        parser = LogParser()

        if parts[0] == "--baseline":
            if len(parts) < 3:
                return "Usage: /log-anomaly --baseline <baseline-file> <file>"
            bl_path = parts[1]
            filepath = parts[2]
            if not os.path.isfile(bl_path):
                return f"Baseline file not found: {bl_path}"
            if not os.path.isfile(filepath):
                return f"File not found: {filepath}"
            with open(bl_path, encoding="utf-8", errors="replace") as f:
                bl_parsed = parser.parse(f.read())
            baseline = detector.build_baseline(bl_parsed.entries)
            detector.set_baseline(baseline)
            with open(filepath, encoding="utf-8", errors="replace") as f:
                parsed = parser.parse(f.read())
            report = detector.detect(parsed.entries)
            lines = [
                f"Anomalies: {report.count} (baseline: {len(bl_parsed.entries)} entries)",
                f"Max score: {report.max_score:.2f}",
            ]
            for a in report.anomalies[:10]:
                lines.append(f"  [{a.score:.2f}] {a.anomaly_type.value}: {a.description[:80]}")
            return "\n".join(lines)

        filepath = parts[0]
        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"
        with open(filepath, encoding="utf-8", errors="replace") as f:
            parsed = parser.parse(f.read())
        report = detector.detect(parsed.entries)
        lines = [
            f"Entries: {report.total_entries}",
            f"Anomalies: {report.count}",
        ]
        for a in report.anomalies[:10]:
            lines.append(f"  [{a.score:.2f}] {a.anomaly_type.value}: {a.description[:80]}")
        if not report.anomalies:
            lines.append("  No anomalies detected (no baseline set).")
        return "\n".join(lines)

    registry.register_async("log-anomaly", "Detect log anomalies and unusual patterns", log_anomaly_handler)

    # ------------------------------------------------------------------
    # /log-dashboard — Log visualization dashboard
    # ------------------------------------------------------------------
    async def log_dashboard_handler(args: str) -> str:
        """
        Usage: /log-dashboard <file>
               /log-dashboard export <file> [--json]
               /log-dashboard drill-down <file> --service <svc> [--level <lvl>]
        """
        from lidco.logintel.dashboard import LogDashboard
        from lidco.logintel.parser import LogParser

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /log-dashboard <subcommand>\n"
                "  <file>                            show dashboard\n"
                "  export <file> [--json]            export dashboard data\n"
                "  drill-down <file> --service <s>   drill down by service/level"
            )

        parser = LogParser()
        dashboard = LogDashboard()

        subcmd = parts[0].lower()

        if subcmd == "export":
            if len(parts) < 2:
                return "Usage: /log-dashboard export <file> [--json]"
            filepath = parts[1]
            if not os.path.isfile(filepath):
                return f"File not found: {filepath}"
            with open(filepath, encoding="utf-8", errors="replace") as f:
                parsed = parser.parse(f.read())
            data = dashboard.build(parsed.entries)
            if "--json" in parts:
                return dashboard.export_json(data)
            return dashboard.export_text(data)

        if subcmd == "drill-down":
            if len(parts) < 2:
                return "Usage: /log-dashboard drill-down <file> --service <s>"
            filepath = parts[1]
            if not os.path.isfile(filepath):
                return f"File not found: {filepath}"
            with open(filepath, encoding="utf-8", errors="replace") as f:
                parsed = parser.parse(f.read())
            svc = None
            lvl = None
            if "--service" in parts:
                idx = parts.index("--service")
                if idx + 1 < len(parts):
                    svc = parts[idx + 1]
            if "--level" in parts:
                idx = parts.index("--level")
                if idx + 1 < len(parts):
                    lvl = parts[idx + 1]
            filtered = dashboard.drill_down(parsed.entries, service=svc, level=lvl)
            lines = [f"Drill-down results: {len(filtered)} entries"]
            for e in filtered[:15]:
                lines.append(f"  {e.timestamp} [{e.source}] {e.level}: {e.message[:80]}")
            if len(filtered) > 15:
                lines.append(f"  ... and {len(filtered) - 15} more")
            return "\n".join(lines)

        # Default: treat as file path
        filepath = parts[0]
        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"
        with open(filepath, encoding="utf-8", errors="replace") as f:
            parsed = parser.parse(f.read())
        data = dashboard.build(parsed.entries)
        return dashboard.export_text(data)

    registry.register_async("log-dashboard", "Log visualization and dashboard", log_dashboard_handler)
