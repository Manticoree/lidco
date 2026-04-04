"""Q282 CLI commands: /cot-plan, /cot-execute, /cot-optimize, /cot-visualize."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q282 slash commands."""

    async def cot_plan_handler(args: str) -> str:
        from lidco.cot.planner import CoTPlanner

        planner = _state.setdefault("planner", CoTPlanner())
        if not args.strip():
            return json.dumps(planner.summary(), indent=2)
        steps = planner.decompose(args)
        return f"Planned {len(steps)} steps for: {args[:60]}"

    async def cot_execute_handler(args: str) -> str:
        from lidco.cot.executor import StepExecutor

        planner = _state.get("planner")
        if not planner:
            return "No plan. Use /cot-plan first."
        executor = _state.setdefault("executor", StepExecutor())
        ready = planner.ready_steps()
        if not ready:
            return "No ready steps. All done or dependencies unmet."
        step = ready[0]
        result_text = args.strip() or f"Result for {step.description}"
        executor.execute(step, result_text)
        return f"Executed {step.step_id}: {step.description[:60]}"

    async def cot_optimize_handler(args: str) -> str:
        from lidco.cot.optimizer import CoTOptimizer

        planner = _state.get("planner")
        if not planner:
            return "No plan to optimize."
        optimizer = CoTOptimizer()
        result = optimizer.optimize(planner.steps())
        return f"Optimized: {result.original_steps} -> {result.optimized_steps} steps, saved ~{result.estimated_savings_tokens} tokens"

    async def cot_visualize_handler(args: str) -> str:
        from lidco.cot.visualizer import CoTVisualizer

        planner = _state.get("planner")
        if not planner:
            return "No plan to visualize."
        viz = CoTVisualizer()
        fmt = args.strip() or "text"
        if fmt == "mermaid":
            return viz.as_mermaid(planner.steps())
        if fmt == "json":
            return json.dumps(viz.as_json(planner.steps()), indent=2)
        return viz.as_text_tree(planner.steps())

    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("cot-plan", "Plan reasoning steps", cot_plan_handler))
    registry.register(SlashCommand("cot-execute", "Execute reasoning steps", cot_execute_handler))
    registry.register(SlashCommand("cot-optimize", "Optimize reasoning chain", cot_optimize_handler))
    registry.register(SlashCommand("cot-visualize", "Visualize reasoning chain", cot_visualize_handler))
