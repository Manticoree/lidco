"""Q153 CLI commands: /perf."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q153 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def perf_handler(args: str) -> str:
        from lidco.perf.timing_profiler import TimingProfiler
        from lidco.perf.memory_tracker import MemoryTracker
        from lidco.perf.bottleneck_detector import BottleneckDetector
        from lidco.perf.perf_report import PerfReport

        if "profiler" not in _state:
            _state["profiler"] = TimingProfiler()
        if "tracker" not in _state:
            _state["tracker"] = MemoryTracker()
        if "detector" not in _state:
            _state["detector"] = BottleneckDetector()
        if "report" not in _state:
            _state["report"] = PerfReport()

        profiler: TimingProfiler = _state["profiler"]  # type: ignore[assignment]
        tracker: MemoryTracker = _state["tracker"]  # type: ignore[assignment]
        detector: BottleneckDetector = _state["detector"]  # type: ignore[assignment]
        report: PerfReport = _state["report"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "time":
            return _handle_time(profiler, rest)
        if sub == "memory":
            return _handle_memory(tracker, rest)
        if sub == "bottleneck":
            return _handle_bottleneck(profiler, detector, rest)
        if sub == "report":
            return _handle_report(profiler, report, rest)

        return (
            "Usage: /perf <subcommand>\n"
            "  time start <name>   — start a timer\n"
            "  time stop <id>      — stop a timer\n"
            "  time summary        — show timing summary\n"
            "  time slowest [n]    — show slowest operations\n"
            "  time clear          — clear timings\n"
            "  memory snapshot [l] — take memory snapshot\n"
            "  memory peak         — show peak memory\n"
            "  memory report       — show memory report\n"
            "  memory clear        — clear snapshots\n"
            "  bottleneck analyze  — analyze timing bottlenecks\n"
            "  bottleneck suggest  — suggest optimizations\n"
            "  report summary      — performance summary\n"
            "  report trend        — performance trend"
        )

    registry.register(SlashCommand("perf", "Performance monitoring", perf_handler))


def _handle_time(profiler, rest: str) -> str:
    parts = rest.strip().split(maxsplit=1)
    action = parts[0].lower() if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""

    if action == "start":
        name = arg or "unnamed"
        tid = profiler.start(name)
        return f"Timer started: {tid} ({name})"
    if action == "stop":
        if not arg:
            return "Usage: /perf time stop <timing_id>"
        try:
            rec = profiler.stop(arg)
            return f"Stopped '{rec.name}': {rec.elapsed * 1000:.2f} ms"
        except KeyError as exc:
            return str(exc)
    if action == "summary":
        s = profiler.summary()
        if not s:
            return "No timing records."
        return json.dumps(s, indent=2)
    if action == "slowest":
        n = int(arg) if arg.isdigit() else 5
        slow = profiler.slowest(n)
        if not slow:
            return "No timing records."
        lines = [f"  {r.name}: {r.elapsed * 1000:.2f} ms" for r in slow]
        return "Slowest operations:\n" + "\n".join(lines)
    if action == "clear":
        profiler.clear()
        return "Timing records cleared."

    return f"Timing records: {len(profiler.records)}"


def _handle_memory(tracker, rest: str) -> str:
    parts = rest.strip().split(maxsplit=1)
    action = parts[0].lower() if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""

    if action == "snapshot":
        label = arg or "manual"
        snap = tracker.snapshot(label)
        return f"Snapshot '{snap.label}': {snap.rss_bytes} bytes (delta: {snap.delta_bytes})"
    if action == "peak":
        p = tracker.peak()
        if p is None:
            return "No snapshots recorded."
        return f"Peak memory: {p.rss_bytes} bytes ({p.label})"
    if action == "report":
        return tracker.format_report()
    if action == "clear":
        tracker.clear()
        return "Memory snapshots cleared."

    return f"Snapshots: {len(tracker.snapshots)}"


def _handle_bottleneck(profiler, detector, rest: str) -> str:
    parts = rest.strip().split(maxsplit=1)
    action = parts[0].lower() if parts else ""

    records = profiler.records
    if action == "analyze":
        bottlenecks = detector.analyze(records)
        if not bottlenecks:
            return "No bottlenecks detected."
        return detector.format_report(bottlenecks)
    if action == "suggest":
        bottlenecks = detector.analyze(records)
        suggestions = detector.suggest_optimizations(bottlenecks)
        if not suggestions:
            return "No suggestions."
        return "\n".join(f"  - {s}" for s in suggestions)

    bns = detector.top_bottlenecks(records)
    return f"Bottlenecks: {len(bns)}"


def _handle_report(profiler, report, rest: str) -> str:
    parts = rest.strip().split(maxsplit=1)
    action = parts[0].lower() if parts else ""

    records = profiler.records
    if action == "summary":
        summary = report.compute(records)
        return report.format_summary(summary)
    if action == "trend":
        summary = report.compute(records)
        return f"Trend: {report.trend([summary])}"

    summary = report.compute(records)
    return report.format_summary(summary)
