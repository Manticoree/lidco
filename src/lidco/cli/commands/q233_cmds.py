"""Q233 CLI commands: /session-budget, /turn-budget, /budget-checkpoint, /session-report."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q233 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /session-budget
    # ------------------------------------------------------------------

    async def session_budget_handler(args: str) -> str:
        from lidco.budget.session_init import SessionInitializer

        parts = args.strip().split()
        sub = parts[0].lower() if parts else "init"

        init = SessionInitializer()

        if sub == "init":
            model = parts[1] if len(parts) > 1 else ""
            limit = int(parts[2]) if len(parts) > 2 else 0
            result = init.initialize(model=model, context_limit=limit)
            return init.summary(result)

        if sub == "estimate":
            text = " ".join(parts[1:]) if len(parts) > 1 else ""
            tokens = init.estimate_system_tokens(text)
            return f"Estimated tokens: {tokens:,}"

        if sub == "recommend":
            limit = int(parts[1]) if len(parts) > 1 else 128000
            recs = init.recommend_reserves(limit)
            lines = [f"Recommended reserves for {limit:,} context:"]
            for k, v in recs.items():
                lines.append(f"  {k}: {v:,}")
            return "\n".join(lines)

        return (
            "Usage: /session-budget <subcommand>\n"
            "  init [model] [limit]  — initialize budget\n"
            "  estimate <text>       — estimate token count\n"
            "  recommend [limit]     — recommend reserves"
        )

    # ------------------------------------------------------------------
    # /turn-budget
    # ------------------------------------------------------------------

    async def turn_budget_handler(args: str) -> str:
        from lidco.budget.turn_manager import TurnBudgetManager

        if not hasattr(turn_budget_handler, "_mgr"):
            turn_budget_handler._mgr = TurnBudgetManager()  # type: ignore[attr-defined]
        mgr: TurnBudgetManager = turn_budget_handler._mgr  # type: ignore[attr-defined]

        parts = args.strip().split()
        sub = parts[0].lower() if parts else "summary"

        if sub == "begin":
            tokens = int(parts[1]) if len(parts) > 1 else 0
            turn = mgr.begin_turn(tokens)
            return f"Turn {turn} started at {tokens:,} tokens."

        if sub == "end":
            tokens = int(parts[1]) if len(parts) > 1 else 0
            compacted = "compact" in args.lower()
            tb = mgr.end_turn(tokens, compacted=compacted)
            return f"Turn {tb.turn} ended. Delta: {tb.delta:+,} tokens."

        if sub == "recent":
            count = int(parts[1]) if len(parts) > 1 else 5
            recent = mgr.get_recent(count)
            if not recent:
                return "No turns recorded yet."
            lines = [f"Last {len(recent)} turn(s):"]
            for t in recent:
                lines.append(f"  Turn {t.turn}: {t.pre_tokens:,} -> {t.post_tokens:,} (delta {t.delta:+,})")
            return "\n".join(lines)

        return mgr.summary()

    # ------------------------------------------------------------------
    # /budget-checkpoint
    # ------------------------------------------------------------------

    async def budget_checkpoint_handler(args: str) -> str:
        from lidco.budget.checkpoint import BudgetCheckpointManager

        if not hasattr(budget_checkpoint_handler, "_mgr"):
            budget_checkpoint_handler._mgr = BudgetCheckpointManager()  # type: ignore[attr-defined]
        mgr: BudgetCheckpointManager = budget_checkpoint_handler._mgr  # type: ignore[attr-defined]

        parts = args.strip().split()
        sub = parts[0].lower() if parts else "summary"

        if sub == "save":
            sid = parts[1] if len(parts) > 1 else "default"
            tokens = int(parts[2]) if len(parts) > 2 else 0
            cp = mgr.save(session_id=sid, tokens_used=tokens)
            return f"Checkpoint saved for '{cp.session_id}' at {cp.tokens_used:,} tokens."

        if sub == "load":
            sid = parts[1] if len(parts) > 1 else "default"
            cp = mgr.load(sid)
            if cp is None:
                return f"No checkpoint found for '{sid}'."
            return f"Loaded: {cp.session_id} — {cp.tokens_used:,} tokens, turn {cp.turns}"

        if sub == "clear":
            mgr.clear()
            return "All checkpoints cleared."

        return mgr.summary()

    # ------------------------------------------------------------------
    # /session-report
    # ------------------------------------------------------------------

    async def session_report_handler(args: str) -> str:
        from lidco.budget.session_report import SessionReportGenerator

        if not hasattr(session_report_handler, "_gen"):
            session_report_handler._gen = SessionReportGenerator()  # type: ignore[attr-defined]
        gen: SessionReportGenerator = session_report_handler._gen  # type: ignore[attr-defined]

        parts = args.strip().split()
        sub = parts[0].lower() if parts else "generate"

        if sub == "generate":
            sid = parts[1] if len(parts) > 1 else "session"
            total = int(parts[2]) if len(parts) > 2 else 50000
            limit = int(parts[3]) if len(parts) > 3 else 128000
            report = gen.generate(session_id=sid, total=total, limit=limit, peak=total)
            return gen.format_report(report)

        if sub == "export":
            sid = parts[1] if len(parts) > 1 else "session"
            report = gen.generate(session_id=sid, total=50000, limit=128000)
            data = gen.export(report)
            return str(data)

        return gen.summary()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    registry.register(SlashCommand("session-budget", "Initialize session token budget", session_budget_handler))
    registry.register(SlashCommand("turn-budget", "Per-turn budget tracking", turn_budget_handler))
    registry.register(SlashCommand("budget-checkpoint", "Save/restore budget checkpoints", budget_checkpoint_handler))
    registry.register(SlashCommand("session-report", "End-of-session budget report", session_report_handler))
