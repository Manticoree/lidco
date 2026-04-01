"""Q185 CLI commands: /feature-dev, /explore-code, /architect, /feature-summary."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:  # noqa: C901
    """Register Q185 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /feature-dev
    # ------------------------------------------------------------------

    async def feature_dev_handler(args: str) -> str:
        from lidco.feature_dev.phases import Phase
        from lidco.feature_dev.workflow import FeatureDevWorkflow

        parts = args.strip().split(maxsplit=1)
        if not parts:
            wf = _state.get("feature_wf")
            if wf is None:
                return "No active feature workflow. Usage: /feature-dev <name> [description]"
            return (
                f"Feature: {wf.name} | Phase: {wf.current_phase.value} | "
                f"Complete: {wf.is_complete} | History: {len(wf.history)} phases"
            )

        sub = parts[0].lower()

        if sub == "run-all":
            wf = _state.get("feature_wf")
            if wf is None:
                return "No active workflow. Create one first: /feature-dev <name> <desc>"
            results = wf.run_all()
            lines = [f"Ran {len(results)} phases:"]
            for r in results:
                lines.append(f"  {r.phase.value}: {r.status.value} ({r.duration_ms}ms)")
            return "\n".join(lines)

        if sub == "skip":
            wf = _state.get("feature_wf")
            if wf is None:
                return "No active workflow."
            phase_name = parts[1].strip().upper() if len(parts) > 1 else ""
            try:
                phase = Phase(phase_name.lower())
            except ValueError:
                return f"Unknown phase: {phase_name}. Valid: {', '.join(p.value for p in Phase)}"
            wf = wf.skip_phase(phase)
            _state["feature_wf"] = wf
            return f"Phase {phase.value} will be skipped"

        if sub == "next":
            wf = _state.get("feature_wf")
            if wf is None:
                return "No active workflow."
            if wf.is_complete:
                return "Workflow already complete."
            result = wf.run_phase(wf.current_phase)
            return f"{result.phase.value}: {result.status.value} — {result.output}"

        # Create new workflow: /feature-dev <name> [description]
        name = parts[0]
        desc = parts[1] if len(parts) > 1 else ""
        wf = FeatureDevWorkflow(name, desc)
        _state["feature_wf"] = wf
        return f"Created feature workflow '{name}' — 7 phases ready"

    # ------------------------------------------------------------------
    # /explore-code
    # ------------------------------------------------------------------

    async def explore_code_handler(args: str) -> str:
        from lidco.feature_dev.explorer import CodeExplorerAgent

        parts = args.strip().split()
        if not parts:
            return "Usage: /explore-code <path> [focus1 focus2 ...]"

        path = parts[0]
        focus = tuple(parts[1:])
        agent = CodeExplorerAgent()
        result = agent.explore(path, focus)
        return (
            f"Explored {result.root}: {result.files_found} files, "
            f"{len(result.focus_hits)} focus hits\n{result.summary}"
        )

    # ------------------------------------------------------------------
    # /architect
    # ------------------------------------------------------------------

    async def architect_handler(args: str) -> str:
        from lidco.feature_dev.architect import CodeArchitectAgent

        if not args.strip():
            return "Usage: /architect <requirements>"

        agent = CodeArchitectAgent()
        proposals = agent.propose(args.strip())
        best = agent.recommend(proposals)
        blueprint = agent.generate_blueprint(best)

        lines = [
            f"Recommended: {best.name} (complexity: {best.complexity_score})",
            f"Description: {best.description}",
            f"Trade-offs: {'; '.join(best.trade_offs)}",
            "",
            "Blueprint:",
            f"  Components: {', '.join(blueprint.components)}",
            f"  Files to create: {', '.join(blueprint.files_to_create)}",
            f"  Files to modify: {', '.join(blueprint.files_to_modify)}",
            f"  Steps: {len(blueprint.steps)}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /feature-summary
    # ------------------------------------------------------------------

    async def feature_summary_handler(args: str) -> str:
        wf = _state.get("feature_wf")
        if wf is None:
            return "No active feature workflow."

        lines = [f"Feature: {wf.name}", f"Description: {wf.description}", ""]
        for r in wf.history:
            lines.append(
                f"  [{r.status.value:>7}] {r.phase.value}: {r.output[:80]} "
                f"({r.duration_ms}ms)"
            )
        if not wf.history:
            lines.append("  No phases executed yet.")
        lines.append(f"\nComplete: {wf.is_complete}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    registry.register(SlashCommand("feature-dev", "7-phase feature development workflow", feature_dev_handler))
    registry.register(SlashCommand("explore-code", "Explore codebase structure", explore_code_handler))
    registry.register(SlashCommand("architect", "Generate architecture proposals", architect_handler))
    registry.register(SlashCommand("feature-summary", "Show feature workflow summary", feature_summary_handler))
