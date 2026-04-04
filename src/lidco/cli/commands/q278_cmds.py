"""Q278 CLI commands — /profile-run, /flamegraph, /hotspots, /memory-profile

Registered via register_q278_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q278_commands(registry) -> None:
    """Register Q278 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /profile-run <code_snippet>
    # ------------------------------------------------------------------
    async def profile_run_handler(args: str) -> str:
        from lidco.profiler.runner import ProfileRunner

        code = args.strip()
        if not code:
            return "Usage: /profile-run <code_snippet>"
        runner = ProfileRunner()
        result = runner.profile(code)
        lines = [
            f"Profile: {result.name}",
            f"Total time: {result.total_time:.4f}ms",
            f"Call count: {result.call_count}",
            f"Entries: {len(result.entries)}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /flamegraph [from-latest | render | export]
    # ------------------------------------------------------------------
    async def flamegraph_handler(args: str) -> str:
        from lidco.profiler.flamegraph import FlameGraphGenerator
        from lidco.profiler.runner import ProfileRunner

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "from-latest"

        runner = ProfileRunner()
        gen = FlameGraphGenerator()

        if subcmd == "from-latest":
            code = " ".join(parts[1:]) if len(parts) > 1 else "x = 1\ny = 2"
            result = runner.profile(code)
            root = gen.from_profile(result)
            return gen.render_text(root)

        if subcmd == "render":
            code = " ".join(parts[1:]) if len(parts) > 1 else "a = 1"
            result = runner.profile(code)
            root = gen.from_profile(result)
            return gen.render_text(root)

        if subcmd == "export":
            code = " ".join(parts[1:]) if len(parts) > 1 else "a = 1"
            result = runner.profile(code)
            root = gen.from_profile(result)
            return gen.export_json(root)

        return (
            "Usage: /flamegraph <subcommand>\n"
            "  from-latest [code]  generate from code\n"
            "  render [code]       render ASCII\n"
            "  export [code]       export JSON"
        )

    # ------------------------------------------------------------------
    # /hotspots [find [limit] | by-calls [limit] | suggest]
    # ------------------------------------------------------------------
    async def hotspots_handler(args: str) -> str:
        from lidco.profiler.hotspots import HotspotFinder
        from lidco.profiler.runner import ProfileRunner

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "find"

        runner = ProfileRunner()
        finder = HotspotFinder()
        # Use a sample profile for demonstration
        result = runner.profile("for i in range(10):\n  print(i)\nresult = sorted(data)")

        if subcmd == "find":
            limit = int(parts[1]) if len(parts) > 1 else 10
            hotspots = finder.find(result, limit=limit)
            lines = [f"Top {len(hotspots)} hotspots by time:"]
            for h in hotspots:
                lines.append(f"  {h.function_name} — {h.time_ms:.2f}ms ({h.percentage:.1f}%)")
            return "\n".join(lines)

        if subcmd == "by-calls":
            limit = int(parts[1]) if len(parts) > 1 else 10
            hotspots = finder.by_calls(result, limit=limit)
            lines = [f"Top {len(hotspots)} hotspots by calls:"]
            for h in hotspots:
                lines.append(f"  {h.function_name} — {h.call_count} calls")
            return "\n".join(lines)

        if subcmd == "suggest":
            hotspots = finder.find(result, limit=3)
            lines = ["Optimisation suggestions:"]
            for h in hotspots:
                s = finder.suggest_optimization(h)
                lines.append(f"  {h.function_name}: {s}")
            return "\n".join(lines)

        return (
            "Usage: /hotspots <subcommand>\n"
            "  find [limit]      top by time\n"
            "  by-calls [limit]  top by call count\n"
            "  suggest           optimisation hints"
        )

    # ------------------------------------------------------------------
    # /memory-profile [snapshot [label] | allocate <source> <bytes> | leaks | top | trend]
    # ------------------------------------------------------------------
    async def memory_profile_handler(args: str) -> str:
        from lidco.profiler.memory import MemoryProfiler

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "snapshot"

        mp = MemoryProfiler()

        if subcmd == "snapshot":
            label = parts[1] if len(parts) > 1 else ""
            snap = mp.snapshot(label)
            return (
                f"Snapshot taken — total: {snap.total_bytes} bytes, "
                f"peak: {snap.peak_bytes} bytes"
            )

        if subcmd == "allocate":
            if len(parts) < 3:
                return "Usage: /memory-profile allocate <source> <bytes>"
            source = parts[1]
            try:
                nbytes = int(parts[2])
            except ValueError:
                return "Error: bytes must be an integer."
            mp.record_allocation(source, nbytes)
            return f"Recorded allocation: {source} +{nbytes} bytes"

        if subcmd == "leaks":
            leaks = mp.detect_leaks()
            if not leaks:
                return "No leaks detected."
            lines = ["Potential leaks:"]
            for lk in leaks:
                lines.append(f"  {lk['source']}: +{lk['growth_bytes']} bytes")
            return "\n".join(lines)

        if subcmd == "top":
            top = mp.top_allocators()
            if not top:
                return "No allocations recorded."
            lines = ["Top allocators:"]
            for src, nbytes in top:
                lines.append(f"  {src}: {nbytes} bytes")
            return "\n".join(lines)

        if subcmd == "trend":
            trend = mp.growth_trend()
            if not trend:
                return "No snapshots recorded."
            lines = ["Memory trend:"]
            for t in trend:
                lines.append(f"  {t['total_bytes']} bytes (peak: {t['peak_bytes']})")
            return "\n".join(lines)

        return (
            "Usage: /memory-profile <subcommand>\n"
            "  snapshot [label]           take memory snapshot\n"
            "  allocate <source> <bytes>  record allocation\n"
            "  leaks                      detect memory leaks\n"
            "  top                        top allocators\n"
            "  trend                      memory growth trend"
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("profile-run", "Profile a code snippet", profile_run_handler))
    registry.register(SlashCommand("flamegraph", "Generate flame graph", flamegraph_handler))
    registry.register(SlashCommand("hotspots", "Find performance hotspots", hotspots_handler))
    registry.register(SlashCommand("memory-profile", "Memory allocation profiling", memory_profile_handler))
