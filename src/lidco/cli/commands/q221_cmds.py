"""Q221 CLI commands: /stream-mode, /stream-replay, /stream-export, /progress."""
from __future__ import annotations


def register(registry) -> None:  # noqa: ANN001
    """Register Q221 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /stream-mode
    # ------------------------------------------------------------------

    async def stream_mode_handler(args: str) -> str:
        from lidco.streaming.fanout_multiplexer import FanOutMultiplexer, OutputTarget

        mux = FanOutMultiplexer()
        parts = args.strip().split()
        if not parts:
            return "Usage: /stream-mode <add|remove|list> [name] [type]"
        action = parts[0].lower()
        if action == "list":
            return mux.summary()
        if action == "add" and len(parts) >= 3:
            name = parts[1]
            try:
                target_type = OutputTarget(parts[2])
            except ValueError:
                return f"Unknown target type: {parts[2]}. Use: terminal, file, websocket, callback"
            dest = parts[3] if len(parts) > 3 else ""
            cfg = mux.add_target(name, target_type, dest)
            return f"Added target: {cfg.name} ({cfg.target_type.value})"
        if action == "remove" and len(parts) >= 2:
            removed = mux.remove_target(parts[1])
            return f"Removed: {parts[1]}" if removed else f"Target not found: {parts[1]}"
        return "Usage: /stream-mode <add|remove|list> [name] [type]"

    # ------------------------------------------------------------------
    # /stream-replay
    # ------------------------------------------------------------------

    async def stream_replay_handler(args: str) -> str:
        from lidco.streaming.event_replay import EventReplay

        replay = EventReplay()
        action = args.strip().lower()
        if action == "start":
            replay.start_recording()
            return "Recording started."
        if action == "stop":
            count = replay.stop_recording()
            return f"Recording stopped. {count} events captured."
        if action == "clear":
            replay.clear()
            return "Journal cleared."
        return replay.summary()

    # ------------------------------------------------------------------
    # /stream-export
    # ------------------------------------------------------------------

    async def stream_export_handler(args: str) -> str:
        import json
        from lidco.streaming.event_replay import EventReplay

        replay = EventReplay()
        entries = replay.export()
        if not entries:
            return "No events to export."
        return json.dumps(entries, indent=2)

    # ------------------------------------------------------------------
    # /progress
    # ------------------------------------------------------------------

    async def progress_handler(args: str) -> str:
        from lidco.streaming.progress_reporter import ProgressReporter

        reporter = ProgressReporter()
        parts = args.strip().split()
        if not parts:
            return reporter.summary()
        action = parts[0].lower()
        if action == "start" and len(parts) >= 2:
            task_name = parts[1]
            total = int(parts[2]) if len(parts) > 2 else 0
            entry = reporter.start(task_name, total=total)
            return f"Started: {entry.task} (total={entry.total})"
        if action == "update" and len(parts) >= 3:
            task_name = parts[1]
            current = int(parts[2])
            entry = reporter.update(task_name, current)
            if entry is None:
                return f"Unknown task: {task_name}"
            return f"Updated: {entry.task} {entry.current}/{entry.total}"
        if action == "complete" and len(parts) >= 2:
            entry = reporter.complete(parts[1])
            if entry is None:
                return f"Unknown task: {parts[1]}"
            return f"Completed: {entry.task}"
        return "Usage: /progress [start|update|complete] <task> [value]"

    registry.register(
        SlashCommand("stream-mode", "Manage stream output targets", stream_mode_handler)
    )
    registry.register(
        SlashCommand("stream-replay", "Record/replay stream events", stream_replay_handler)
    )
    registry.register(
        SlashCommand("stream-export", "Export recorded events as JSON", stream_export_handler)
    )
    registry.register(
        SlashCommand("progress", "Track task progress", progress_handler)
    )
