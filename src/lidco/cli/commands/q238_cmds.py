"""Q238 CLI commands: /ultraplan, /ultrareview, /turn-limit, /parallel-tools."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q238 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /ultraplan
    # ------------------------------------------------------------------

    async def ultraplan_handler(args: str) -> str:
        from lidco.modes.ultra_planner import UltraPlanner

        planner = UltraPlanner()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "create":
            if not rest:
                return "Usage: /ultraplan create <title>: <description>"
            if ":" in rest:
                title, desc = rest.split(":", 1)
                title, desc = title.strip(), desc.strip()
            else:
                title, desc = rest, rest
            plan = planner.create_plan(title, desc)
            return planner.to_markdown(plan)

        if sub == "critique":
            if not rest:
                return "Usage: /ultraplan critique <title>"
            plan = planner.create_plan(rest, rest)
            issues = planner.critique(plan)
            if not issues:
                return "No issues found."
            return "Critique:\n" + "\n".join(f"- {i}" for i in issues)

        if sub == "summary":
            if not rest:
                return "Usage: /ultraplan summary <title>"
            plan = planner.create_plan(rest, rest)
            return planner.summary(plan)

        return (
            "Usage: /ultraplan <subcommand>\n"
            "  create <title>: <desc> — create a new plan\n"
            "  critique <title>       — critique a plan\n"
            "  summary <title>        — summarize a plan"
        )

    # ------------------------------------------------------------------
    # /ultrareview
    # ------------------------------------------------------------------

    async def ultrareview_handler(args: str) -> str:
        from lidco.modes.ultra_reviewer import UltraReviewer

        reviewer = UltraReviewer()
        source = args.strip()
        if not source:
            return "Usage: /ultrareview <source code>"
        review = reviewer.review(source)
        if not review.findings:
            return "No findings."
        lines = [reviewer.summary(review)]
        for f in review.findings:
            lines.append(
                f"  [{f.severity}] {f.perspective.value} L{f.line}: {f.message}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /turn-limit
    # ------------------------------------------------------------------

    async def turn_limit_handler(args: str) -> str:
        from lidco.safety.turn_limiter import TurnLimiter

        limiter = TurnLimiter()
        parts = args.strip().split()
        sub = parts[0].lower() if parts else ""

        if sub == "check":
            turn = int(parts[1]) if len(parts) > 1 else 0
            result = limiter.check(turn)
            return f"{result.action.value}: {result.message}" if result.message else result.action.value

        if sub == "set":
            limit = int(parts[1]) if len(parts) > 1 else 100
            limiter.set_limit(limit)
            return f"Turn limit set to {limit}."

        if sub == "status":
            turn = int(parts[1]) if len(parts) > 1 else 0
            return limiter.summary(turn)

        return (
            "Usage: /turn-limit <subcommand>\n"
            "  check <turn>  — check if turn is within limit\n"
            "  set <limit>   — set the turn limit\n"
            "  status <turn> — show current status"
        )

    # ------------------------------------------------------------------
    # /parallel-tools
    # ------------------------------------------------------------------

    async def parallel_tools_handler(args: str) -> str:
        from lidco.tools.parallel_runner import ParallelToolRunner

        runner = ParallelToolRunner()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "simulate":
            if not rest:
                return "Usage: /parallel-tools simulate <tool1> <tool2> ..."
            tool_names = rest.split()
            calls = [runner.add_call(t) for t in tool_names]
            result = runner.simulate_run(calls)
            return runner.summary(result)

        if sub == "detect":
            if not rest:
                return "Usage: /parallel-tools detect <tool1> <tool2> ..."
            tool_names = rest.split()
            calls = [runner.add_call(t) for t in tool_names]
            batches = runner.detect_dependencies(calls)
            lines = [f"{len(batches)} batch(es):"]
            for i, batch in enumerate(batches):
                names = ", ".join(c.tool_name for c in batch)
                lines.append(f"  Batch {i + 1}: {names}")
            return "\n".join(lines)

        return (
            "Usage: /parallel-tools <subcommand>\n"
            "  simulate <tools...> — simulate parallel execution\n"
            "  detect <tools...>   — detect dependency batches"
        )

    registry.register(SlashCommand("ultraplan", "Multi-pass ultra planning", ultraplan_handler))
    registry.register(SlashCommand("ultrareview", "Deep 6-perspective code review", ultrareview_handler))
    registry.register(SlashCommand("turn-limit", "Conversation turn limits", turn_limit_handler))
    registry.register(SlashCommand("parallel-tools", "Parallel tool execution", parallel_tools_handler))
