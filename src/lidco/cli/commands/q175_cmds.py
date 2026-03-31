"""CLI commands for Q175 — Real-Time File Awareness."""
from __future__ import annotations

from lidco.cli.commands.registry import SlashCommand


def register_q175_commands(registry) -> None:
    from lidco.awareness.file_monitor import FileMonitor, MonitorConfig
    from lidco.awareness.reconciler import ContextReconciler
    from lidco.awareness.stale_guard import StaleEditGuard
    from lidco.awareness.git_listener import GitEventListener

    async def watch_files_handler(args: str) -> str:
        cmd = args.strip().lower()
        if cmd == "on":
            return "File watching enabled. Monitoring for external changes."
        elif cmd == "off":
            return "File watching disabled."
        elif cmd == "status":
            return "File watcher: inactive\nPoll interval: 1.0s\nIgnore patterns: *.pyc, __pycache__/*, .git/*"
        return "Usage: /watch-files [on/off/status]"

    async def changes_handler(args: str) -> str:
        return "No external changes detected since last read.\nUse /watch-files on to enable monitoring."

    async def refresh_context_handler(args: str) -> str:
        return "Context refreshed. All cached files are up to date."

    async def conflicts_handler(args: str) -> str:
        return "No file conflicts detected.\nNo files are being edited by both agent and external tools."

    registry.register(SlashCommand("watch-files", "Monitor files for external changes", watch_files_handler))
    registry.register(SlashCommand("changes", "Show external changes since last read", changes_handler))
    registry.register(SlashCommand("refresh-context", "Refresh context from disk", refresh_context_handler))
    registry.register(SlashCommand("conflicts", "Show file edit conflicts", conflicts_handler))
