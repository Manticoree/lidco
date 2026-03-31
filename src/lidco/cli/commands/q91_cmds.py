"""Q91 CLI commands: session-history, smart-apply, ignore, mem-compact, plugins."""

from pathlib import Path


def register_q91_commands(registry):
    """Register Q91 slash commands."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /session-history [search query]
    # ------------------------------------------------------------------
    async def session_history_handler(args: str) -> str:
        from lidco.memory.session_history import SessionHistoryStore
        store = SessionHistoryStore()
        args = args.strip()
        if args:
            result = store.search(args)
            if not result.records:
                return f"No sessions matching '{args}'."
            lines = [f"Sessions matching '{args}':"]
            for r in result.records:
                lines.append(f"  [{r.session_id[:8]}] {r.topic} ({r.turn_count} turns)")
            return "\n".join(lines)
        else:
            records = store.list(limit=10)
            if not records:
                return "No session history found."
            lines = ["Recent sessions (newest first):"]
            for r in records:
                lines.append(f"  [{r.session_id[:8]}] {r.topic} ({r.turn_count} turns)")
            return "\n".join(lines)

    registry.register(SlashCommand(
        "session-history",
        "List or search past sessions. Usage: /session-history [query]",
        session_history_handler,
    ))

    # ------------------------------------------------------------------
    # /smart-apply [--dry-run]
    # ------------------------------------------------------------------
    async def smart_apply_handler(args: str) -> str:
        from lidco.editing.smart_apply import SmartApply
        dry_run = "--dry-run" in args
        sa = SmartApply(project_root=".")
        # Try to get last assistant message from context
        last_text = getattr(registry, "_last_assistant_message", "")
        if not last_text:
            return "No recent assistant message to apply code from."
        results = sa.apply_all(last_text, dry_run=dry_run)
        if not results:
            return "No applicable code blocks found in last response."
        lines = [f"{'[dry-run] ' if dry_run else ''}Smart apply results:"]
        for r in results:
            status = "would apply" if dry_run else ("applied" if r.applied else "failed")
            lines.append(f"  {status}: {r.file_path}")
            if r.error:
                lines.append(f"    error: {r.error}")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "smart-apply",
        "Apply code blocks from last LLM response to target files. [--dry-run]",
        smart_apply_handler,
    ))

    # ------------------------------------------------------------------
    # /ignore [add|remove|list] [pattern]
    # ------------------------------------------------------------------
    async def ignore_handler(args: str) -> str:
        from lidco.context.exclude_file import ContextExcludeFile
        ef = ContextExcludeFile(".")
        parts = args.strip().split(None, 1)
        sub = parts[0].lower() if parts else "list"
        pattern = parts[1] if len(parts) > 1 else ""

        if sub == "add":
            if not pattern:
                return "Usage: /ignore add <pattern>"
            ef.add_pattern(pattern)
            return f"Added ignore pattern: {pattern}"
        elif sub == "remove":
            if not pattern:
                return "Usage: /ignore remove <pattern>"
            removed = ef.remove_pattern(pattern)
            return f"Removed: {pattern}" if removed else f"Pattern not found: {pattern}"
        else:  # list or default
            patterns = ef.list_patterns()
            if not patterns:
                return "No .lidcoignore patterns configured."
            lines = [".lidcoignore patterns:"]
            for p in patterns:
                prefix = "!" if p.negated else " "
                lines.append(f"  {prefix}{p.pattern}")
            return "\n".join(lines)

    registry.register(SlashCommand(
        "ignore",
        "Manage .lidcoignore patterns. Usage: /ignore [add|remove|list] [pattern]",
        ignore_handler,
    ))

    # ------------------------------------------------------------------
    # /mem-compact [--dry-run]
    # ------------------------------------------------------------------
    async def mem_compact_handler(args: str) -> str:
        from lidco.memory.consolidator import MemoryConsolidator
        dry_run = "--dry-run" in args.lower()
        consolidator = MemoryConsolidator()

        # Try to use AgentMemoryStore if available
        try:
            from lidco.memory.agent_memory import AgentMemoryStore
            store = AgentMemoryStore()
            if dry_run:
                report = consolidator.dry_run(store)
            else:
                report = consolidator.consolidate(store)
            return report.summary
        except Exception as e:
            return f"Memory consolidation unavailable: {e}"

    registry.register(SlashCommand(
        "mem-compact",
        "Consolidate similar/stale memory entries. [--dry-run]",
        mem_compact_handler,
    ))

    # ------------------------------------------------------------------
    # /plugins [list|reload]
    # ------------------------------------------------------------------
    async def plugins_handler(args: str) -> str:
        from lidco.tools.plugin_loader import ToolPluginLoader
        loader = ToolPluginLoader(".")
        sub = args.strip().lower()

        manifest = loader.load_all()
        lines = [manifest.format_summary()]
        for p in manifest.plugins:
            status = "✓" if p.loaded else "✗"
            lines.append(f"  {status} {p.name}  {p.source_path}")
            if not p.loaded and p.error:
                lines.append(f"      error: {p.error}")
        if not manifest.plugins:
            lines.append("  No plugins found in .lidco/tools/")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "plugins",
        "List loaded tool plugins from .lidco/tools/. Usage: /plugins [list|reload]",
        plugins_handler,
    ))
