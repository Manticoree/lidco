"""Q133 CLI commands: /debug."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q133 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def debug_handler(args: str) -> str:
        from lidco.debug.call_trace import CallTracer
        from lidco.debug.state_inspector import StateInspector
        from lidco.debug.error_aggregator import ErrorAggregator
        from lidco.debug.execution_log import ExecutionLog

        # Lazy init
        if "tracer" not in _state:
            _state["tracer"] = CallTracer()
        if "inspector" not in _state:
            _state["inspector"] = StateInspector()
        if "aggregator" not in _state:
            _state["aggregator"] = ErrorAggregator()
        if "log" not in _state:
            _state["log"] = ExecutionLog()

        tracer: CallTracer = _state["tracer"]  # type: ignore[assignment]
        inspector: StateInspector = _state["inspector"]  # type: ignore[assignment]
        aggregator: ErrorAggregator = _state["aggregator"]  # type: ignore[assignment]
        xlog: ExecutionLog = _state["log"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "trace":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "summary":
                return json.dumps(tracer.summary(), indent=2)
            if action == "clear":
                tracer.clear()
                return "Trace cleared."
            if action == "last":
                fn_name = sub_parts[1] if len(sub_parts) > 1 else None
                entry = tracer.last(fn_name)
                if entry is None:
                    return "No trace entries."
                return f"{entry.fn_name}: result={entry.result!r}, elapsed={entry.elapsed:.4f}s, error={entry.error!r}"
            entries = tracer.entries()
            return f"Trace entries: {len(entries)}\n" + json.dumps(tracer.summary(), indent=2)

        if sub == "inspect":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "capture":
                if len(sub_parts) < 2:
                    return "Usage: /debug inspect capture <json_data>"
                try:
                    data = json.loads(sub_parts[1])
                except json.JSONDecodeError:
                    return "Invalid JSON."
                snap = inspector.capture(data, label="cli")
                return f"Captured snapshot {snap.id[:8]}."
            if action == "list":
                snaps = inspector.list_snapshots()
                return f"Snapshots: {len(snaps)}"
            if action == "clear":
                inspector.clear()
                return "Inspector cleared."
            return "Usage: /debug inspect capture|list|clear"

        if sub == "errors":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "summary":
                return json.dumps(aggregator.summary(), indent=2)
            if action == "top":
                n = 5
                if len(sub_parts) > 1:
                    try:
                        n = int(sub_parts[1])
                    except ValueError:
                        pass
                top = aggregator.top(n)
                lines = [f"Top {n} errors:"]
                for r in top:
                    lines.append(f"  [{r.error_type}] {r.message!r} x{r.count}")
                return "\n".join(lines)
            if action == "clear":
                aggregator.clear()
                return "Error records cleared."
            return json.dumps(aggregator.summary(), indent=2)

        if sub == "log":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "add":
                if len(sub_parts) < 2:
                    return "Usage: /debug log add <level> <message>"
                msg_parts = sub_parts[1].split(maxsplit=1)
                level = msg_parts[0] if msg_parts else "info"
                message = msg_parts[1] if len(msg_parts) > 1 else ""
                xlog.log(level, message)
                return f"Logged [{level}]: {message}"
            if action == "tail":
                n = 20
                if len(sub_parts) > 1:
                    try:
                        n = int(sub_parts[1])
                    except ValueError:
                        pass
                entries = xlog.tail(n)
                lines = [f"Last {len(entries)} log entries:"]
                for e in entries:
                    lines.append(f"  [{e.level.upper()}] {e.message}")
                return "\n".join(lines)
            if action == "clear":
                xlog.clear()
                return "Log cleared."
            return f"Log entries: {len(xlog)}"

        return (
            "Usage: /debug <sub>\n"
            "  trace summary|clear|last [fn]   -- call trace info\n"
            "  inspect capture|list|clear       -- state snapshots\n"
            "  errors summary|top [n]|clear     -- error aggregator\n"
            "  log add|tail [n]|clear           -- execution log"
        )

    registry.register(SlashCommand("debug", "Agent introspection & debugging (Q133)", debug_handler))
