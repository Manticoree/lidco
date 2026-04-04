"""Q286 CLI commands: /tool-analyze, /tool-plan, /cache-advice, /tool-compose."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q286 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # Shared state across commands within a single registration.
    _state: dict[str, object] = {}

    def _get_analyzer():
        if "analyzer" not in _state:
            from lidco.tool_opt.analyzer import ToolUseAnalyzer
            _state["analyzer"] = ToolUseAnalyzer()
        return _state["analyzer"]

    def _get_planner():
        if "planner" not in _state:
            from lidco.tool_opt.planner import ToolPlanner
            _state["planner"] = ToolPlanner()
        return _state["planner"]

    def _get_advisor():
        if "advisor" not in _state:
            from lidco.tool_opt.cache_advisor import ToolCacheAdvisor
            _state["advisor"] = ToolCacheAdvisor()
        return _state["advisor"]

    def _get_composer():
        if "composer" not in _state:
            from lidco.tool_opt.composition import ToolComposition
            _state["composer"] = ToolComposition()
        return _state["composer"]

    # ------------------------------------------------------------------
    # /tool-analyze
    # ------------------------------------------------------------------

    async def tool_analyze_handler(args: str) -> str:
        analyzer = _get_analyzer()
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "record":
            if len(parts) < 2:
                return "Usage: /tool-analyze record <tool_name> [duration]"
            tool_name = parts[1]
            duration = 0.0
            if len(parts) > 2:
                try:
                    duration = float(parts[2])
                except ValueError:
                    return "Duration must be a number."
            analyzer.record_call(tool_name, {}, duration)
            return f"Recorded call to {tool_name} (duration={duration}s)."

        if sub == "score":
            return f"Efficiency score: {analyzer.efficiency_score()}"

        if sub == "unnecessary":
            calls = analyzer.unnecessary_calls()
            if not calls:
                return "No unnecessary calls detected."
            lines = [f"  {c.tool_name}({c.args})" for c in calls]
            return f"Unnecessary calls ({len(calls)}):\n" + "\n".join(lines)

        if sub == "missed":
            hints = analyzer.missed_opportunities()
            if not hints:
                return "No missed opportunities."
            return "\n".join(f"  - {h}" for h in hints)

        if sub == "summary":
            s = analyzer.summary()
            return (
                f"Total calls: {s['total_calls']}\n"
                f"Efficiency: {s['efficiency_score']}\n"
                f"Unnecessary: {s['unnecessary_calls']}\n"
                f"Duration: {s['total_duration']}s\n"
                f"Tools: {s['tool_counts']}"
            )

        if sub == "reset":
            _state.pop("analyzer", None)
            return "Analyzer reset."

        return (
            "Usage: /tool-analyze <subcommand>\n"
            "  record <tool> [duration] — record a call\n"
            "  score                    — efficiency score\n"
            "  unnecessary              — list unnecessary calls\n"
            "  missed                   — missed optimisation hints\n"
            "  summary                  — full summary\n"
            "  reset                    — clear history"
        )

    # ------------------------------------------------------------------
    # /tool-plan
    # ------------------------------------------------------------------

    async def tool_plan_handler(args: str) -> str:
        planner = _get_planner()
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "add":
            if len(parts) < 2:
                return "Usage: /tool-plan add <tool> [depends_on_idx,...]"
            tool = parts[1]
            deps: list[int] = []
            if len(parts) > 2:
                try:
                    deps = [int(x) for x in parts[2].split(",") if x.strip()]
                except ValueError:
                    return "depends_on must be comma-separated integers."
            idx = planner.add_call(tool, {}, deps)
            return f"Added call #{idx}: {tool} (deps={deps})."

        if sub == "order":
            ordered = planner.plan()
            if not ordered:
                return "No calls planned."
            lines = [f"  {c._index}: {c.tool}" for c in ordered]
            return "Execution order:\n" + "\n".join(lines)

        if sub == "parallel":
            groups = planner.parallelizable()
            if not groups:
                return "No calls to parallelize."
            lines = []
            for i, grp in enumerate(groups):
                names = ", ".join(c.tool for c in grp)
                lines.append(f"  Layer {i}: [{names}]")
            return "Parallel groups:\n" + "\n".join(lines)

        if sub == "optimize":
            plan = planner.optimize()
            lines = [
                f"Ordered: {len(plan.ordered)} calls",
                f"Parallel layers: {len(plan.parallel_groups)}",
                f"Read batches: {len(plan.batched_reads)}",
            ]
            return "\n".join(lines)

        if sub == "reset":
            _state.pop("planner", None)
            return "Planner reset."

        return (
            "Usage: /tool-plan <subcommand>\n"
            "  add <tool> [deps]  — add a planned call\n"
            "  order              — topological execution order\n"
            "  parallel           — parallel groups\n"
            "  optimize           — full optimised plan\n"
            "  reset              — clear plan"
        )

    # ------------------------------------------------------------------
    # /cache-advice
    # ------------------------------------------------------------------

    async def cache_advice_handler(args: str) -> str:
        advisor = _get_advisor()
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "record":
            if len(parts) < 2:
                return "Usage: /cache-advice record <tool> [result]"
            tool = parts[1]
            result = parts[2] if len(parts) > 2 else ""
            advisor.record_call(tool, {}, result)
            return f"Recorded {tool} call."

        if sub == "suggest":
            suggestions = advisor.suggest_cache()
            if not suggestions:
                return "No caching suggestions."
            return "\n".join(f"  - {s}" for s in suggestions)

        if sub == "repeated":
            repeated = advisor.detect_repeated()
            if not repeated:
                return "No repeated calls."
            lines = [f"  {t}({a}) x{c}" for t, a, c in repeated]
            return "Repeated calls:\n" + "\n".join(lines)

        if sub == "savings":
            s = advisor.estimate_savings()
            return (
                f"Total: {s['total_calls']}, "
                f"Cacheable: {s['cacheable_calls']}, "
                f"Saved ratio: {s['saved_ratio']}"
            )

        if sub == "reset":
            _state.pop("advisor", None)
            return "Cache advisor reset."

        return (
            "Usage: /cache-advice <subcommand>\n"
            "  record <tool> [result] — record a call\n"
            "  suggest                — caching suggestions\n"
            "  repeated               — detect repeated calls\n"
            "  savings                — estimate savings\n"
            "  reset                  — clear history"
        )

    # ------------------------------------------------------------------
    # /tool-compose
    # ------------------------------------------------------------------

    async def tool_compose_handler(args: str) -> str:
        composer = _get_composer()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "add":
            rest = parts[1].strip() if len(parts) > 1 else ""
            if not rest:
                return "Usage: /tool-compose add <tool>"
            composer.add_step(rest)
            return f"Added step: {rest}."

        if sub == "chain":
            pipeline = composer.chain()
            if not pipeline.steps:
                return "No steps to chain."
            names = " -> ".join(s.name for s in pipeline.steps)
            return f"Pipeline: {names}"

        if sub == "clear":
            composer.clear()
            return "Pipeline cleared."

        if sub == "list":
            pipeline = composer.chain()
            if not pipeline.steps:
                return "No steps."
            lines = [f"  {i}: {s.name}" for i, s in enumerate(pipeline.steps)]
            return "Steps:\n" + "\n".join(lines)

        return (
            "Usage: /tool-compose <subcommand>\n"
            "  add <tool>  — add a pipeline step\n"
            "  chain       — show the pipeline\n"
            "  list        — list all steps\n"
            "  clear       — clear pipeline"
        )

    registry.register(SlashCommand("tool-analyze", "Analyze tool usage patterns", tool_analyze_handler))
    registry.register(SlashCommand("tool-plan", "Plan and optimize tool call order", tool_plan_handler))
    registry.register(SlashCommand("cache-advice", "Suggest caching for repeated tool calls", cache_advice_handler))
    registry.register(SlashCommand("tool-compose", "Compose tools into pipelines", tool_compose_handler))
