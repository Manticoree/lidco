"""Q220 CLI commands: /agent-dag, /agent-results, /agent-budget, /agent-cancel."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q220 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /agent-dag
    # ------------------------------------------------------------------

    async def agent_dag_handler(args: str) -> str:
        from lidco.agents.dag_runner import AgentDAGRunner

        runner = AgentDAGRunner()
        if not args.strip():
            return "Usage: /agent-dag <node_id> <agent_name> [dep1,dep2,...]"
        parts = args.strip().split()
        node_id = parts[0]
        agent_name = parts[1] if len(parts) > 1 else node_id
        deps = tuple(parts[2].split(",")) if len(parts) > 2 else ()
        runner.add_node(id=node_id, agent_name=agent_name, depends_on=deps)
        return runner.summary()

    # ------------------------------------------------------------------
    # /agent-results
    # ------------------------------------------------------------------

    async def agent_results_handler(args: str) -> str:
        from lidco.agents.result_aggregator import ResultAggregator

        agg = ResultAggregator()
        if not args.strip():
            return "Usage: /agent-results <agent_name> <content>"
        parts = args.strip().split(maxsplit=1)
        name = parts[0]
        content = parts[1] if len(parts) > 1 else ""
        agg.add_result(agent_name=name, content=content)
        return agg.summary()

    # ------------------------------------------------------------------
    # /agent-budget
    # ------------------------------------------------------------------

    async def agent_budget_handler(args: str) -> str:
        from lidco.agents.budget_splitter import BudgetSplitter, SplitMode

        if not args.strip():
            return "Usage: /agent-budget <total_tokens> <agent1,agent2,...> [mode]"
        parts = args.strip().split()
        total = int(parts[0])
        agents = parts[1].split(",") if len(parts) > 1 else []
        mode_str = parts[2] if len(parts) > 2 else "equal"
        mode = SplitMode(mode_str)
        splitter = BudgetSplitter(total_tokens=total)
        allocations = splitter.split(agents, mode=mode)
        return splitter.summary(allocations)

    # ------------------------------------------------------------------
    # /agent-cancel
    # ------------------------------------------------------------------

    async def agent_cancel_handler(args: str) -> str:
        from lidco.agents.cancellation import CancellationManager

        mgr = CancellationManager()
        if not args.strip():
            return "Usage: /agent-cancel <agent_id>"
        agent_id = args.strip().split()[0]
        mgr.cancel(agent_id)
        return mgr.summary()

    registry.register(
        SlashCommand("agent-dag", "Build and run agent DAGs", agent_dag_handler)
    )
    registry.register(
        SlashCommand("agent-results", "Aggregate agent results", agent_results_handler)
    )
    registry.register(
        SlashCommand("agent-budget", "Split budget across agents", agent_budget_handler)
    )
    registry.register(
        SlashCommand("agent-cancel", "Cancel running agents", agent_cancel_handler)
    )
