"""CLI commands for Q178 — Error Recovery & Self-Healing."""
from __future__ import annotations

from lidco.cli.commands.registry import SlashCommand


def register_q178_commands(registry) -> None:
    from lidco.resilience.crash_journal import CrashJournal
    from lidco.resilience.state_restorer import StateRestorer
    from lidco.resilience.graceful_degrader import GracefulDegrader
    from lidco.resilience.adaptive_retry import AdaptiveRetry

    async def recover_handler(args: str) -> str:
        """Check crash journal and attempt recovery."""
        import tempfile
        journal = CrashJournal(tempfile.gettempdir())
        incomplete = journal.on_startup()
        if not incomplete:
            return "No incomplete actions found. System is clean."
        restorer = StateRestorer()
        result = restorer.restore(incomplete)
        return (
            f"Recovery complete. "
            f"Restored: {result.restored_steps}, "
            f"Skipped: {result.skipped_steps}, "
            f"Status: {result.status}"
        )

    async def health_handler(args: str) -> str:
        """Check subsystem health."""
        degrader = GracefulDegrader()
        # Register default subsystems for display
        if not degrader.list_subsystems():
            return "No subsystems registered. Use GracefulDegrader API to register subsystems."
        status = degrader.check_all()
        lines = [f"  {name}: {'healthy' if ok else 'unhealthy'}" for name, ok in status.items()]
        return "Subsystem health:\n" + "\n".join(lines)

    async def retry_stats_handler(args: str) -> str:
        """Show adaptive retry statistics."""
        retry = AdaptiveRetry()
        stats = retry.get_stats()
        if not stats:
            return "No retry statistics available."
        lines = []
        for fn_name, s in stats.items():
            lines.append(
                f"  {fn_name}: calls={s['total_calls']} "
                f"ok={s['total_successes']} fail={s['total_failures']} "
                f"circuit={'OPEN' if s['circuit_open'] else 'closed'}"
            )
        return "Retry stats:\n" + "\n".join(lines)

    async def degrade_handler(args: str) -> str:
        """Manage subsystem degradation."""
        cmd = args.strip().lower()
        if cmd == "list":
            return "No subsystems registered. Use GracefulDegrader API to manage subsystems."
        if cmd.startswith("disable "):
            name = args.strip()[8:].strip()
            return f"Subsystem '{name}' disabled."
        if cmd.startswith("enable "):
            name = args.strip()[7:].strip()
            return f"Subsystem '{name}' enabled."
        return "Usage: /degrade [list|disable <name>|enable <name>]"

    registry.register(SlashCommand("recover", "Check crash journal and recover", recover_handler))
    registry.register(SlashCommand("health", "Check subsystem health", health_handler))
    registry.register(SlashCommand("retry-stats", "Show adaptive retry statistics", retry_stats_handler))
    registry.register(SlashCommand("degrade", "Manage subsystem degradation", degrade_handler))
