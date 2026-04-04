"""Q285 CLI commands — /goal, /subtasks, /goal-progress, /validate-goal

Registered via register_q285_commands(registry).
"""
from __future__ import annotations

import shlex

# Module-level state shared across handlers
_state: dict = {
    "last_goal": None,
    "last_subtasks": None,
    "monitor": None,
}


def register_q285_commands(registry) -> None:
    """Register Q285 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /goal <text>
    # ------------------------------------------------------------------
    async def goal_handler(args: str) -> str:
        from lidco.goals.parser import GoalParser

        text = args.strip()
        if not text:
            return "Usage: /goal <goal description>"
        parser = GoalParser()
        goal = parser.parse(text)
        _state["last_goal"] = goal
        lines = [
            f"Goal: {goal.name}",
            f"Priority: {goal.priority}",
            f"Criteria: {len(goal.acceptance_criteria)}",
        ]
        for c in goal.acceptance_criteria:
            lines.append(f"  - {c}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /subtasks [generate | graph | effort]
    # ------------------------------------------------------------------
    async def subtasks_handler(args: str) -> str:
        from lidco.goals.subtasks import SubtaskGenerator

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "generate"

        goal = _state.get("last_goal")
        if goal is None:
            return "No goal set. Run /goal first."

        gen = SubtaskGenerator()

        if subcmd == "generate":
            subtasks = gen.generate(goal)
            _state["last_subtasks"] = subtasks
            lines = [f"Generated {len(subtasks)} subtask(s):"]
            for st in subtasks:
                dep_str = f" (depends on: {', '.join(st.depends_on)})" if st.depends_on else ""
                lines.append(f"  [{st.id}] {st.description} — effort: {st.effort_estimate}{dep_str}")
            return "\n".join(lines)

        if subcmd == "graph":
            subtasks = _state.get("last_subtasks")
            if not subtasks:
                subtasks = gen.generate(goal)
                _state["last_subtasks"] = subtasks
            graph = gen.dependency_graph(subtasks)
            lines = ["Dependency graph:"]
            for sid, deps in graph.items():
                dep_str = ", ".join(deps) if deps else "(none)"
                lines.append(f"  {sid} -> {dep_str}")
            return "\n".join(lines)

        if subcmd == "effort":
            subtasks = _state.get("last_subtasks")
            if not subtasks:
                subtasks = gen.generate(goal)
                _state["last_subtasks"] = subtasks
            total = gen.estimate_effort(subtasks)
            return f"Total effort estimate: {total:.1f} points across {len(subtasks)} subtask(s)"

        return (
            "Usage: /subtasks <subcommand>\n"
            "  generate   decompose goal into subtasks\n"
            "  graph      show dependency graph\n"
            "  effort     estimate total effort"
        )

    # ------------------------------------------------------------------
    # /goal-progress [status | update <id> <status> | blocker <desc>]
    # ------------------------------------------------------------------
    async def goal_progress_handler(args: str) -> str:
        from lidco.goals.monitor import ProgressMonitor

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "status"

        monitor = _state.get("monitor")
        if monitor is None:
            monitor = ProgressMonitor()
            _state["monitor"] = monitor
            # Auto-populate from last subtasks
            subtasks = _state.get("last_subtasks")
            if subtasks:
                for st in subtasks:
                    monitor.add_subtask(st.id)

        if subcmd == "status":
            rpt = monitor.report()
            lines = [
                f"Progress: {rpt['completion_pct']:.1f}%",
                f"  done: {rpt['done']}, in_progress: {rpt['in_progress']}, "
                f"pending: {rpt['pending']}, blocked: {rpt['blocked']}",
            ]
            if rpt["blockers"]:
                lines.append("Blockers:")
                for b in rpt["blockers"]:
                    lines.append(f"  - {b}")
            return "\n".join(lines)

        if subcmd == "update":
            if len(parts) < 3:
                return "Usage: /goal-progress update <subtask_id> <status>"
            sid, status = parts[1], parts[2]
            try:
                monitor.update(sid, status)
            except (KeyError, ValueError) as exc:
                return f"Error: {exc}"
            return f"Updated {sid} -> {status}"

        if subcmd == "blocker":
            desc = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not desc:
                return "Usage: /goal-progress blocker <description>"
            monitor.add_blocker(desc)
            return f"Blocker added: {desc}"

        return (
            "Usage: /goal-progress <subcommand>\n"
            "  status                    show progress report\n"
            "  update <id> <status>      update subtask status\n"
            "  blocker <description>     add a blocker"
        )

    # ------------------------------------------------------------------
    # /validate-goal [full | partial <threshold>]
    # ------------------------------------------------------------------
    async def validate_goal_handler(args: str) -> str:
        from lidco.goals.validator import GoalValidator

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "full"

        goal = _state.get("last_goal")
        if goal is None:
            return "No goal set. Run /goal first."

        monitor = _state.get("monitor")
        validator = GoalValidator()

        # Build results from monitor state
        results: dict[str, bool] = {}
        if monitor and goal.acceptance_criteria:
            for criterion in goal.acceptance_criteria:
                # Check if any subtask mapped to this criterion is done
                results[criterion] = False
            subtasks = _state.get("last_subtasks", [])
            for idx, criterion in enumerate(goal.acceptance_criteria):
                if idx < len(subtasks):
                    sid = subtasks[idx].id
                    st_status = monitor._statuses.get(sid)
                    if st_status and st_status.status == "done":
                        results[criterion] = True

        if subcmd == "full":
            vr = validator.validate(goal, results)
            status = "PASSED" if vr.passed else "FAILED"
            lines = [f"Validation: {status}"]
            if vr.criteria_met:
                lines.append("Met:")
                for c in vr.criteria_met:
                    lines.append(f"  + {c}")
            if vr.criteria_failed:
                lines.append("Failed:")
                for c in vr.criteria_failed:
                    lines.append(f"  - {c}")
            return "\n".join(lines)

        if subcmd == "partial":
            threshold = float(parts[1]) if len(parts) > 1 else 0.5
            vr = validator.validate_partial(goal, results, threshold)
            status = "PASSED" if vr.passed else "FAILED"
            return f"Partial validation ({threshold:.0%} threshold): {status}"

        return (
            "Usage: /validate-goal <subcommand>\n"
            "  full                  validate all criteria\n"
            "  partial [threshold]   validate with pass threshold"
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("goal", "Parse a goal from text", goal_handler))
    registry.register(SlashCommand("subtasks", "Decompose goal into subtasks", subtasks_handler))
    registry.register(SlashCommand("goal-progress", "Track goal progress", goal_progress_handler))
    registry.register(SlashCommand("validate-goal", "Validate goal completion", validate_goal_handler))
