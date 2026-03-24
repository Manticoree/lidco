"""CLI commands for Q89 — Turbo Mode & Autonomous Execution.

/turbo        — manage turbo mode (enable/disable/status/add-allowed/add-blocked)
/role-agent   — dispatch a role-specialized sub-agent
/mem-search   — semantic memory search
/horizon      — long-horizon task planner (plan/run/status/resume)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.cli.commands.registry import CommandRegistry, SlashCommand


def register_turbo_commands(registry: "CommandRegistry") -> None:
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # Shared state stored on the registry instance
    # ------------------------------------------------------------------
    if not hasattr(registry, "_turbo_runner"):
        registry._turbo_runner = None  # type: ignore[attr-defined]
    if not hasattr(registry, "_role_factory"):
        registry._role_factory = None  # type: ignore[attr-defined]
    if not hasattr(registry, "_sem_memory"):
        registry._sem_memory = None  # type: ignore[attr-defined]
    if not hasattr(registry, "_horizon_planner"):
        registry._horizon_planner = None  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # /turbo
    # ------------------------------------------------------------------
    async def turbo_handler(args: str = "") -> str:
        from lidco.execution.turbo_runner import TurboRunner

        parts = args.strip().split(None, 1)
        sub = parts[0].lower() if parts else "status"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "enable":
            registry._turbo_runner = TurboRunner()
            return "Turbo mode ENABLED — commands matching the allowlist will execute without confirmation."

        if sub == "disable":
            registry._turbo_runner = None
            return "Turbo mode DISABLED."

        if sub == "status":
            if registry._turbo_runner is None:
                return "Turbo mode: OFF"
            summary = registry._turbo_runner.summary()
            return (
                "Turbo mode: ON\n"
                f"  History: {summary['total']} commands "
                f"({summary['succeeded']} OK, {summary['blocked']} blocked, "
                f"{summary['denied']} denied, {summary['failed']} failed)"
            )

        if sub == "add-allowed" and rest:
            if registry._turbo_runner is None:
                registry._turbo_runner = TurboRunner()
            registry._turbo_runner.add_allowed(rest)
            return f"Added allowed pattern: {rest}"

        if sub == "add-blocked" and rest:
            if registry._turbo_runner is None:
                registry._turbo_runner = TurboRunner()
            registry._turbo_runner.add_blocked(rest)
            return f"Added blocked pattern: {rest}"

        if sub == "run" and rest:
            if registry._turbo_runner is None:
                return "Turbo mode is OFF. Use `/turbo enable` first."
            result = registry._turbo_runner.run(rest)
            if result.blocked:
                return f"BLOCKED: {result.stderr}"
            if not result.approved:
                return f"DENIED: {result.stderr}"
            if result.dry_run:
                return f"DRY-RUN: {rest}"
            return result.output or f"(exit {result.returncode})"

        return (
            "Usage: /turbo enable|disable|status\n"
            "       /turbo add-allowed <regex>\n"
            "       /turbo add-blocked <regex>\n"
            "       /turbo run <command>"
        )

    registry.register(SlashCommand("turbo", "Turbo mode: auto-execute pre-approved commands", turbo_handler))

    # ------------------------------------------------------------------
    # /role-agent
    # ------------------------------------------------------------------
    async def role_agent_handler(args: str = "") -> str:
        from lidco.agents.role_agents import RoleAgentFactory, AgentTask

        parts = args.strip().split(None, 1)
        if not parts:
            from lidco.agents.role_agents import VALID_ROLES
            return f"Usage: /role-agent <role> <instructions>\nRoles: {', '.join(VALID_ROLES)}"

        sub = parts[0].lower()

        if sub == "list":
            from lidco.agents.role_agents import VALID_ROLES, ROLE_SYSTEM_PROMPTS
            lines = ["Available roles:"]
            for r in VALID_ROLES:
                preview = ROLE_SYSTEM_PROMPTS[r][:60].replace("\n", " ")
                lines.append(f"  {r:12s} — {preview}…")
            return "\n".join(lines)

        instructions = parts[1] if len(parts) > 1 else ""
        if not instructions:
            return f"Usage: /role-agent {sub} <instructions>"

        if registry._role_factory is None:
            registry._role_factory = RoleAgentFactory()

        try:
            task = AgentTask(role=sub, instructions=instructions)
            result = await registry._role_factory.dispatch(task)
        except ValueError as exc:
            return str(exc)

        if not result.success:
            return f"Role agent '{sub}' failed: {result.error}"
        return f"[{sub.upper()}]\n{result.response}"

    registry.register(SlashCommand("role-agent", "Dispatch a role-specialized sub-agent (coder/reviewer/tester/planner/debugger)", role_agent_handler))

    # ------------------------------------------------------------------
    # /mem-search
    # ------------------------------------------------------------------
    async def mem_search_handler(args: str = "") -> str:
        from lidco.memory.semantic_memory import SemanticMemoryStore

        parts = args.strip().split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            # /mem-search add [priority=N] [ttl=N] key: content
            # Simple format: /mem-search add <key> <content>
            kv = rest.split(None, 1)
            if len(kv) < 2:
                return "Usage: /mem-search add <key> <content>"
            if registry._sem_memory is None:
                registry._sem_memory = SemanticMemoryStore()
            registry._sem_memory.add(kv[0], kv[1])
            return f"Memory entry '{kv[0]}' added."

        if sub == "get":
            if not rest:
                return "Usage: /mem-search get <key>"
            if registry._sem_memory is None:
                return "Memory store is empty."
            entry = registry._sem_memory.get(rest)
            if not entry:
                return f"No entry found for key '{rest}'."
            return f"[{entry.key}] (priority={entry.priority})\n{entry.content}"

        if sub == "stats":
            if registry._sem_memory is None:
                return "Memory store is empty."
            stats = registry._sem_memory.stats()
            return f"Entries: {stats['total']}, with TTL: {stats['with_ttl']}, by priority: {stats['by_priority']}"

        if sub == "purge":
            if registry._sem_memory is None:
                return "Nothing to purge."
            n = registry._sem_memory.purge_expired()
            return f"Purged {n} expired entries."

        # Default: treat the whole args as a search query
        query = args.strip()
        if not query:
            return (
                "Usage: /mem-search <query>\n"
                "       /mem-search add <key> <content>\n"
                "       /mem-search get <key>\n"
                "       /mem-search stats | purge"
            )
        if registry._sem_memory is None:
            return "Memory store is empty. Use `/mem-search add` to populate it."
        results = registry._sem_memory.search(query, top_k=5)
        if not results:
            return "No matching memory entries."
        lines = [f"Search results for '{query}':"]
        for r in results:
            lines.append(f"  [{r.entry.key}] (score={r.score:.3f}, priority={r.entry.priority})")
            lines.append(f"    {r.entry.content[:120]}")
        return "\n".join(lines)

    registry.register(SlashCommand("mem-search", "Semantic memory store: add/get/search entries", mem_search_handler))

    # ------------------------------------------------------------------
    # /horizon
    # ------------------------------------------------------------------
    async def horizon_handler(args: str = "") -> str:
        from lidco.tasks.horizon_planner import HorizonPlanner, StepStatus

        parts = args.strip().split(None, 1)
        sub = parts[0].lower() if parts else "status"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "new":
            if not rest:
                return "Usage: /horizon new <goal description>"
            registry._horizon_planner = HorizonPlanner()
            registry._horizon_planner.set_goal(rest)
            return f"Horizon planner created for goal: {rest}\nUse `/horizon phase <name> <step1>; <step2>; ...` to add phases."

        if registry._horizon_planner is None:
            return "No horizon plan active. Use `/horizon new <goal>` first."

        planner = registry._horizon_planner

        if sub == "phase":
            # /horizon phase <phase-name> <desc1>; <desc2>; ...
            ph_parts = rest.split(None, 1)
            if len(ph_parts) < 2:
                return "Usage: /horizon phase <name> <step1>; <step2>"
            phase_name = ph_parts[0]
            raw_steps = [s.strip() for s in ph_parts[1].split(";") if s.strip()]
            steps = [(f"s{i+1}", desc) for i, desc in enumerate(raw_steps)]
            planner.add_phase(phase_name, steps)
            return f"Phase '{phase_name}' added with {len(steps)} step(s)."

        if sub == "plan":
            return planner.format_plan()

        if sub in ("run", "resume"):
            result = await planner.run(resume=(sub == "resume"))
            status = "SUCCESS" if result.success else "FAILED"
            return (
                f"Horizon run {status}\n"
                f"  Phases: {result.phases_done}/{result.phases_total}\n"
                f"  Steps: {result.steps_done} done, {result.steps_failed} failed\n"
                f"  Elapsed: {result.elapsed:.1f}s"
                + (" (resumed)" if result.resumed else "")
            )

        if sub == "status":
            return planner.format_plan()

        return (
            "Usage: /horizon new <goal>\n"
            "       /horizon phase <name> <step1>; <step2>\n"
            "       /horizon plan | run | resume | status"
        )

    registry.register(SlashCommand("horizon", "Long-horizon task planner with phases, retry, and resume", horizon_handler))
