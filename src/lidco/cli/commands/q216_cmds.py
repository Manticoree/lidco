"""Q216 CLI commands: /profile-analyze, /bottlenecks, /optimize, /memory-check."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q216 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /profile-analyze
    # ------------------------------------------------------------------

    async def profile_analyze_handler(args: str) -> str:
        from lidco.perf_intel.profile_analyzer import ProfileAnalyzer, ProfileEntry

        analyzer = ProfileAnalyzer()
        if not args.strip():
            return "Usage: /profile-analyze <function> <calls> <total_time>"
        parts = args.strip().split()
        name = parts[0]
        calls = int(parts[1]) if len(parts) > 1 else 1
        total = float(parts[2]) if len(parts) > 2 else 0.0
        cum = float(parts[3]) if len(parts) > 3 else total
        per = cum / calls if calls > 0 else 0.0
        entry = ProfileEntry(
            function=name, calls=calls, total_time=total,
            cumulative_time=cum, per_call=per,
        )
        analyzer.add_entry(entry)
        return analyzer.summary()

    # ------------------------------------------------------------------
    # /bottlenecks
    # ------------------------------------------------------------------

    async def bottlenecks_handler(args: str) -> str:
        from lidco.perf_intel.bottleneck_detector import BottleneckDetector

        source = args.strip()
        if not source:
            return "Usage: /bottlenecks <python_source>"
        detector = BottleneckDetector()
        results = detector.detect(source)
        return detector.summary(results)

    # ------------------------------------------------------------------
    # /optimize
    # ------------------------------------------------------------------

    async def optimize_handler(args: str) -> str:
        from lidco.perf_intel.optimization_advisor import OptimizationAdvisor

        source = args.strip()
        if not source:
            return "Usage: /optimize <python_source>"
        advisor = OptimizationAdvisor()
        results = advisor.analyze(source)
        return advisor.summary(results)

    # ------------------------------------------------------------------
    # /memory-check
    # ------------------------------------------------------------------

    async def memory_check_handler(args: str) -> str:
        from lidco.perf_intel.memory_analyzer import MemoryAnalyzer

        source = args.strip()
        if not source:
            return "Usage: /memory-check <python_source>"
        analyzer = MemoryAnalyzer()
        issues = analyzer.detect_leaks(source)
        return analyzer.summary(issues)

    registry.register(
        SlashCommand("profile-analyze", "Analyze profiling data", profile_analyze_handler)
    )
    registry.register(
        SlashCommand("bottlenecks", "Detect performance bottlenecks", bottlenecks_handler)
    )
    registry.register(
        SlashCommand("optimize", "Suggest optimizations", optimize_handler)
    )
    registry.register(
        SlashCommand("memory-check", "Check for memory issues", memory_check_handler)
    )
