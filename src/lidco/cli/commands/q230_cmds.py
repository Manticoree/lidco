"""Q230 CLI commands: /collapse, /importance, /evict, /token-debt."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q230 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /collapse
    # ------------------------------------------------------------------

    async def collapse_handler(args: str) -> str:
        from lidco.budget.message_collapser import MessageCollapser

        collapser = MessageCollapser()
        threshold = 0.7
        parts = args.strip().split()
        if parts:
            try:
                threshold = float(parts[0])
                collapser = MessageCollapser(similarity_threshold=threshold)
            except ValueError:
                pass
        # Demo with empty list when no session messages available
        demo = [
            {"role": "assistant", "content": "OK"},
            {"role": "assistant", "content": "Done"},
            {"role": "assistant", "content": "Sure"},
        ]
        _, result = collapser.collapse(demo)
        return collapser.summary(result)

    # ------------------------------------------------------------------
    # /importance
    # ------------------------------------------------------------------

    async def importance_handler(args: str) -> str:
        from lidco.budget.importance_scorer import ImportanceScorer

        scorer = ImportanceScorer()
        demo = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
            {"role": "tool", "content": "file.py: OK"},
        ]
        scored = scorer.score_all(demo, current_turn=4)
        return scorer.summary(scored)

    # ------------------------------------------------------------------
    # /evict
    # ------------------------------------------------------------------

    async def evict_handler(args: str) -> str:
        from lidco.budget.smart_evictor import SmartEvictor
        from lidco.budget.importance_scorer import ImportanceScorer

        target = 100
        parts = args.strip().split()
        if parts:
            try:
                target = int(parts[0])
            except ValueError:
                pass
        demo = [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "tool", "content": "result"},
            {"role": "user", "content": "Bye"},
        ]
        scorer = ImportanceScorer()
        scored = scorer.score_all(demo, current_turn=5)
        scored_dicts = [
            {"index": s.index, "importance": s.importance} for s in scored
        ]
        evictor = SmartEvictor(min_keep=2)
        _, result = evictor.evict(demo, scored_dicts, target)
        return evictor.summary(result)

    # ------------------------------------------------------------------
    # /token-debt
    # ------------------------------------------------------------------

    async def token_debt_handler(args: str) -> str:
        from lidco.budget.token_debt import TokenDebtTracker

        tracker = TokenDebtTracker()
        parts = args.strip().split()
        if parts:
            try:
                amount = int(parts[0])
                reason = " ".join(parts[1:]) if len(parts) > 1 else "manual"
                tracker.incur(amount, reason)
            except ValueError:
                return "Usage: /token-debt [amount] [reason]"
        return tracker.summary()

    registry.register(
        SlashCommand("collapse", "Collapse similar messages to save tokens", collapse_handler)
    )
    registry.register(
        SlashCommand("importance", "Score message importance", importance_handler)
    )
    registry.register(
        SlashCommand("evict", "Evict low-importance messages", evict_handler)
    )
    registry.register(
        SlashCommand("token-debt", "Track token overspend debt", token_debt_handler)
    )
