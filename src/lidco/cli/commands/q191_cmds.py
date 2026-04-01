"""Q191 CLI commands: /multi-edit, /batch-write, /edit-plan, /transaction."""

from __future__ import annotations

from lidco.cli.commands.registry import SlashCommand


def register_q191_commands(registry) -> None:
    """Register Q191 commands with *registry*."""

    # ------------------------------------------------------------------
    # /multi-edit
    # ------------------------------------------------------------------

    async def multi_edit_handler(args: str) -> str:
        from lidco.editing.multi_edit_engine import MultiEditEngine

        if not args.strip():
            return (
                "Usage: /multi-edit <file_path>\n"
                "Opens a multi-edit session for the specified file.\n"
                "Add edits with old_text -> new_text pairs, then apply."
            )
        path = args.strip()
        try:
            from pathlib import Path

            content = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            return f"Error reading {path}: {exc}"
        engine = MultiEditEngine(path, content)
        return f"Multi-edit session created for {path} ({len(content)} chars). Use /multi-edit apply to execute."

    # ------------------------------------------------------------------
    # /batch-write
    # ------------------------------------------------------------------

    async def batch_write_handler(args: str) -> str:
        from lidco.editing.batch_writer import BatchWriter

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "dry-run":
            writer = BatchWriter()
            plan = writer.dry_run()
            return f"Batch plan: {plan.total} operations queued."

        if not sub:
            return (
                "Usage: /batch-write <subcommand>\n"
                "Subcommands: dry-run\n"
                "Queue file write/delete/mkdir operations and execute as a batch."
            )
        return f"Unknown subcommand: {sub}. Use: dry-run"

    # ------------------------------------------------------------------
    # /edit-plan
    # ------------------------------------------------------------------

    async def edit_plan_handler(args: str) -> str:
        from lidco.editing.edit_planner import EditPlanner

        if not args.strip():
            return (
                "Usage: /edit-plan <file_path>\n"
                "Plan multi-file edits with validation before execution."
            )
        planner = EditPlanner()
        plan = planner.plan()
        return f"Edit plan: {plan.total_edits} edits across {len(plan.groups)} files."

    # ------------------------------------------------------------------
    # /transaction
    # ------------------------------------------------------------------

    async def transaction_handler(args: str) -> str:
        from lidco.editing.transaction import FileTransaction

        sub = args.strip().lower()
        if sub == "status":
            return "No active transaction."
        if not sub:
            return (
                "Usage: /transaction <subcommand>\n"
                "Subcommands: status\n"
                "Manage file transactions with journal-based rollback."
            )
        return f"Unknown subcommand: {sub}. Use: status"

    # -- register ---------------------------------------------------------

    registry.register(SlashCommand("multi-edit", "Apply multiple edits to a single file atomically", multi_edit_handler))
    registry.register(SlashCommand("batch-write", "Queue and execute batch file operations", batch_write_handler))
    registry.register(SlashCommand("edit-plan", "Plan and validate multi-file edits", edit_plan_handler))
    registry.register(SlashCommand("transaction", "File transactions with journal-based rollback", transaction_handler))
