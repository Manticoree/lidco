"""Q240 CLI commands: /stream-stats, /backpressure, /stream-buffer, /flow-control."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q240 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /stream-stats
    # ------------------------------------------------------------------

    async def stream_stats_handler(args: str) -> str:
        from lidco.streaming.stream_monitor import StreamMonitor

        monitor = StreamMonitor()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "record":
            text = parts[1].strip() if len(parts) > 1 else "token"
            monitor.record(text)
            return f"Recorded token: {text!r}"

        if sub == "stall":
            threshold = float(parts[1]) if len(parts) > 1 else 5.0
            stalled = monitor.detect_stall(threshold)
            return f"Stall detected: {stalled}"

        if sub == "anomalies":
            baseline = float(parts[1]) if len(parts) > 1 else None
            alerts = monitor.alert_anomalies(baseline)
            if not alerts:
                return "No anomalies detected."
            return "Anomalies:\n" + "\n".join(f"- {a}" for a in alerts)

        # Default: show stats
        st = monitor.stats()
        lines = [
            "Stream Monitor Stats:",
            f"  TPS: {st['tps']}",
            f"  Total tokens: {st['total_tokens']}",
            f"  Duration: {st['duration']}s",
            f"  Stall detected: {st['stall_detected']}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /backpressure
    # ------------------------------------------------------------------

    async def backpressure_handler(args: str) -> str:
        from lidco.streaming.backpressure import BackpressureController

        controller = BackpressureController()
        parts = args.strip().split()
        sub = parts[0].lower() if parts else ""

        if sub == "check":
            usage = int(parts[1]) if len(parts) > 1 else 0
            signal = controller.check(usage)
            return f"Action: {signal.action}, Buffer usage: {signal.buffer_usage:.2%}"

        if sub == "status":
            st = controller.stats()
            lines = [
                "Backpressure Status:",
                f"  State: {st['state']}",
                f"  Rate limit: {st['rate']} tokens/s",
                f"  High watermark: {st['high_watermark']}",
                f"  Low watermark: {st['low_watermark']}",
                f"  Buffer size: {st['buffer_size']}",
            ]
            return "\n".join(lines)

        return (
            "Usage: /backpressure <subcommand>\n"
            "  check [buffer_usage] — check backpressure signal\n"
            "  status               — show backpressure status"
        )

    # ------------------------------------------------------------------
    # /stream-buffer
    # ------------------------------------------------------------------

    async def stream_buffer_handler(args: str) -> str:
        from lidco.streaming.stream_buffer import StreamBuffer

        buf = StreamBuffer()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "write":
            if not rest:
                return "Usage: /stream-buffer write <data>"
            ok = buf.write(rest)
            return f"Written: {ok}"

        if sub == "read":
            count = int(rest) if rest else 1
            tokens = buf.read(count)
            if not tokens:
                return "Buffer is empty."
            return "Read: " + ", ".join(repr(t) for t in tokens)

        if sub == "drain":
            tokens = buf.drain()
            if not tokens:
                return "Buffer is empty."
            return f"Drained {len(tokens)} token(s)."

        if sub == "stats":
            st = buf.stats()
            lines = [
                "Stream Buffer Stats:",
                f"  Capacity: {st['capacity']}",
                f"  Used: {st['used']}",
                f"  Overflow count: {st['overflow_count']}",
                f"  Total written: {st['total_written']}",
                f"  Total read: {st['total_read']}",
            ]
            return "\n".join(lines)

        return (
            "Usage: /stream-buffer <subcommand>\n"
            "  write <data> — write data to buffer\n"
            "  read [count] — read tokens from buffer\n"
            "  drain        — read all tokens\n"
            "  stats        — show buffer statistics"
        )

    # ------------------------------------------------------------------
    # /flow-control
    # ------------------------------------------------------------------

    async def flow_control_handler(args: str) -> str:
        from lidco.streaming.flow_controller import FlowController

        fc = FlowController()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "status":
            st = fc.stats()
            lines = [
                "Flow Control Status:",
                f"  Congested: {st['is_congested']}",
                f"  Adaptive rate: {st['adaptive_rate']}",
                f"  Produced: {st['produce_count']}",
                f"  Consumed: {st['consume_count']}",
                f"  Rejected: {st['rejected_count']}",
            ]
            return "\n".join(lines)

        if sub == "produce":
            if not rest:
                return "Usage: /flow-control produce <data>"
            ok = fc.produce(rest)
            return f"Produced: {ok}"

        if sub == "consume":
            count = int(rest) if rest else 1
            tokens = fc.consume(count)
            if not tokens:
                return "Nothing to consume."
            return "Consumed: " + ", ".join(repr(t) for t in tokens)

        return (
            "Usage: /flow-control <subcommand>\n"
            "  status          — show flow control status\n"
            "  produce <data>  — produce a token\n"
            "  consume [count] — consume tokens"
        )

    registry.register(SlashCommand("stream-stats", "Stream monitor stats", stream_stats_handler))
    registry.register(SlashCommand("backpressure", "Backpressure control", backpressure_handler))
    registry.register(SlashCommand("stream-buffer", "Stream buffer management", stream_buffer_handler))
    registry.register(SlashCommand("flow-control", "Flow control management", flow_control_handler))
