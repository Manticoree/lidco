"""Q122 CLI commands: /budget."""
from __future__ import annotations

_state: dict = {}


def register(registry) -> None:
    """Register Q122 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def budget_handler(args: str) -> str:
        from lidco.context.token_estimator import TokenEstimator
        from lidco.context.budget_allocator import BudgetAllocator, BudgetSlot
        from lidco.context.message_trimmer import MessageTrimmer
        from lidco.context.context_report import ContextReport

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        # Lazy-init shared components
        if "estimator" not in _state:
            _state["estimator"] = TokenEstimator()
        estimator: TokenEstimator = _state["estimator"]

        if sub == "show":
            budget = int(_state.get("budget", 8192))
            messages = _state.get("messages", [])
            report = ContextReport(budget=budget, estimator=estimator)
            usage = report.measure(messages)
            return report.format(usage)

        if sub == "allocate":
            budget = int(_state.get("budget", 8192))
            allocator = BudgetAllocator(total_budget=budget)
            # Default slots
            allocator.add_slot(BudgetSlot("system", weight=1.0, min_tokens=256))
            allocator.add_slot(BudgetSlot("history", weight=3.0))
            allocator.add_slot(BudgetSlot("context", weight=2.0))
            allocator.add_slot(BudgetSlot("output", weight=1.0, min_tokens=512))
            plan = allocator.allocate()
            lines = [f"Budget: {plan.total} tokens (overflow={plan.overflow})"]
            for name, tokens in plan.slots.items():
                lines.append(f"  {name}: {tokens}")
            return "\n".join(lines)

        if sub == "trim":
            messages = _state.get("messages", [])
            if not messages:
                return "No messages in state. Set _state['messages'] first."
            budget = int(_state.get("budget", 8192))
            trimmer = MessageTrimmer(estimator=estimator)
            result = trimmer.trim(messages, budget)
            _state["messages"] = result.messages
            return (
                f"Trimmed {result.removed_count} message(s), "
                f"saved ~{result.tokens_saved} tokens. "
                f"Remaining: {len(result.messages)} messages."
            )

        return (
            "Usage: /budget <sub>\n"
            "  show      -- show current context usage\n"
            "  allocate  -- show allocation plan for current budget\n"
            "  trim      -- trim messages to budget"
        )

    registry.register(SlashCommand("budget", "Token budget and context allocation", budget_handler))
