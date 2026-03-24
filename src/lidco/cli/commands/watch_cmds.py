"""Slash commands for Watch Mode 3.0 and Architect Mode."""
from __future__ import annotations

from typing import Any

_watch_trigger: Any = None  # module-level singleton


def _get_trigger() -> Any:
    global _watch_trigger
    return _watch_trigger


# ------------------------------------------------------------------
# /watch handlers
# ------------------------------------------------------------------

async def watch_start_handler(args: str = "") -> str:
    """/watch start — begin watching files for AI! / AI? comments."""
    global _watch_trigger
    try:
        from pathlib import Path
        from lidco.watch.agent_trigger import WatchAgentTrigger
        if _watch_trigger and _watch_trigger.running:
            return "Watch mode already running."
        _watch_trigger = WatchAgentTrigger(project_dir=Path.cwd())
        _watch_trigger.start()
        return "Watch mode started. Embed # AI! or # AI? comments in files to trigger the agent."
    except Exception as exc:
        return f"Failed to start watch mode: {exc}"


async def watch_stop_handler(args: str = "") -> str:
    """/watch stop — stop the file watcher."""
    global _watch_trigger
    if _watch_trigger is None or not _watch_trigger.running:
        return "Watch mode is not running."
    _watch_trigger.stop()
    return "Watch mode stopped."


async def watch_status_handler(args: str = "") -> str:
    """/watch status — show current watch mode state."""
    if _watch_trigger is None:
        return "Watch mode: inactive (never started)."
    status = "running" if _watch_trigger.running else "stopped"
    return f"Watch mode: {status}."


# ------------------------------------------------------------------
# /architect handlers
# ------------------------------------------------------------------

async def architect_handler(args: str = "") -> str:
    """/architect <task> — run dual-model plan+execute session."""
    task = args.strip()
    if not task:
        return "Usage: /architect <task description>"
    try:
        from lidco.llm.architect_mode import ArchitectSession
        session = ArchitectSession(
            architect_fn=lambda t: f'{{"rationale":"stub","file_changes":[]}}',
            editor_fn=None,
        )
        plan = session.plan(task)
        results = session.execute(plan)
        lines = [f"Architect plan: {plan.rationale[:200]}"]
        if results:
            lines.append(f"Files changed ({len(results)}):")
            for r in results:
                status = "✓" if r.success else "✗"
                lines.append(f"  {status} {r.file}")
        else:
            lines.append("No file changes in plan.")
        return "\n".join(lines)
    except Exception as exc:
        return f"Architect session failed: {exc}"


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register_watch_commands(registry: Any) -> None:
    from lidco.cli.commands.registry import SlashCommand
    registry.register(SlashCommand("watch start", "Start watch mode (AI!/AI? comments)", watch_start_handler))
    registry.register(SlashCommand("watch stop", "Stop watch mode", watch_stop_handler))
    registry.register(SlashCommand("watch status", "Show watch mode status", watch_status_handler))


def register_architect_commands(registry: Any) -> None:
    from lidco.cli.commands.registry import SlashCommand
    registry.register(SlashCommand("architect", "Run dual-model architect+editor session", architect_handler))
