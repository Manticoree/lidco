"""Q169 CLI commands: /agent-run, /agent-status, /agent-list, /agent-cancel."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def _get_pool():
    """Lazy-init pool manager."""
    from lidco.cloud.agent_spawner import AgentSpawner
    from lidco.cloud.status_tracker import StatusTracker
    from lidco.cloud.pool_manager import AgentPoolManager

    if "pool" not in _state:
        spawner = AgentSpawner()
        tracker = StatusTracker()
        _state["pool"] = AgentPoolManager(spawner, tracker)
    return _state["pool"]


def register(registry) -> None:
    """Register Q169 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def agent_run_handler(args: str) -> str:
        prompt = args.strip()
        if not prompt:
            return "Usage: /agent-run <prompt>"
        pool = _get_pool()
        agent_id = pool.submit(prompt)
        return f"Agent submitted: {agent_id}"

    async def agent_status_handler(args: str) -> str:
        pool = _get_pool()
        agent_id = args.strip()
        if not agent_id:
            s = pool.stats()
            return (
                f"Pool: {s.total} total, {s.running} running, "
                f"{s.queued} queued, {s.completed} completed, {s.failed} failed"
            )
        handle = pool.spawner.get(agent_id)
        if handle is None:
            return f"Unknown agent: {agent_id}"
        log = pool.results(agent_id)
        lines = [f"Agent {agent_id}: {handle.status}"]
        lines.append(f"  Prompt: {handle.prompt}")
        if handle.branch_name:
            lines.append(f"  Branch: {handle.branch_name}")
        if log and log.entries:
            lines.append(f"  Log entries: {len(log.entries)}")
        if log and log.output:
            lines.append(f"  Output: {log.output[:200]}")
        if log and log.error:
            lines.append(f"  Error: {log.error}")
        return "\n".join(lines)

    async def agent_list_handler(args: str) -> str:
        pool = _get_pool()
        agents = pool.spawner.list_all()
        if not agents:
            return "No agents."
        lines = []
        for a in agents:
            lines.append(f"  {a.agent_id}  {a.status:10s}  {a.prompt[:50]}")
        return f"Agents ({len(agents)}):\n" + "\n".join(lines)

    async def agent_cancel_handler(args: str) -> str:
        agent_id = args.strip()
        if not agent_id:
            return "Usage: /agent-cancel <id>"
        pool = _get_pool()
        ok = pool.cancel(agent_id)
        if ok:
            return f"Agent {agent_id} cancelled."
        return f"Cannot cancel agent {agent_id} (not found or already finished)."

    registry.register(SlashCommand("agent-run", "Submit a background agent", agent_run_handler))
    registry.register(SlashCommand("agent-status", "Check agent status", agent_status_handler))
    registry.register(SlashCommand("agent-list", "List all agents", agent_list_handler))
    registry.register(SlashCommand("agent-cancel", "Cancel an agent", agent_cancel_handler))
