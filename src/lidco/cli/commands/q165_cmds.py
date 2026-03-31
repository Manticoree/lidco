"""Q165 CLI commands: /fork, /branch, /branch-diff, /loop (Task 941)."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q165 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /fork [label]
    # ------------------------------------------------------------------

    async def fork_handler(args: str) -> str:
        from lidco.session.branch_manager import BranchManager

        if "branch_mgr" not in _state:
            _state["branch_mgr"] = BranchManager()

        mgr: BranchManager = _state["branch_mgr"]  # type: ignore[assignment]
        label = args.strip() or "fork"

        # Use empty conversation/files when no session context available
        conversation: list[dict] = _state.get("conversation", [])  # type: ignore[assignment]
        files: dict[str, str] = _state.get("files", {})  # type: ignore[assignment]
        active = mgr.get_active()
        parent_id = active.branch_id if active else None

        try:
            branch = mgr.create(label, conversation, files, parent_id=parent_id)
            mgr.switch(branch.branch_id)
            return f"Forked to branch '{branch.name}' ({branch.branch_id})."
        except ValueError as exc:
            return f"Fork failed: {exc}"

    # ------------------------------------------------------------------
    # /branch [list|switch|delete] [name/id]
    # ------------------------------------------------------------------

    async def branch_handler(args: str) -> str:
        from lidco.session.branch_manager import BranchManager

        if "branch_mgr" not in _state:
            _state["branch_mgr"] = BranchManager()

        mgr: BranchManager = _state["branch_mgr"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list" or sub == "":
            branches = mgr.list_branches()
            if not branches:
                return "No branches yet. Use /fork to create one."
            lines = []
            for b in branches:
                marker = " *" if b.is_active else ""
                lines.append(f"  {b.branch_id}  {b.name}{marker}")
            return "Branches:\n" + "\n".join(lines)

        if sub == "switch":
            if not rest:
                return "Usage: /branch switch <branch_id>"
            try:
                branch = mgr.switch(rest)
                return f"Switched to branch '{branch.name}' ({branch.branch_id})."
            except KeyError as exc:
                return str(exc)

        if sub == "delete":
            if not rest:
                return "Usage: /branch delete <branch_id>"
            ok = mgr.delete(rest)
            return f"Deleted branch '{rest}'." if ok else f"Branch '{rest}' not found."

        return (
            "Usage: /branch <subcommand>\n"
            "  list                — list all branches\n"
            "  switch <branch_id>  — switch to branch\n"
            "  delete <branch_id>  — delete a branch"
        )

    # ------------------------------------------------------------------
    # /branch-diff [branch_a] [branch_b]
    # ------------------------------------------------------------------

    async def branch_diff_handler(args: str) -> str:
        from lidco.session.branch_manager import BranchManager
        from lidco.session.branch_diff import BranchDiffEngine

        if "branch_mgr" not in _state:
            _state["branch_mgr"] = BranchManager()

        mgr: BranchManager = _state["branch_mgr"]  # type: ignore[assignment]
        parts = args.strip().split()
        if len(parts) < 2:
            return "Usage: /branch-diff <branch_id_a> <branch_id_b>"

        id_a, id_b = parts[0], parts[1]
        branch_a = mgr.get(id_a)
        branch_b = mgr.get(id_b)
        if branch_a is None:
            return f"Branch '{id_a}' not found."
        if branch_b is None:
            return f"Branch '{id_b}' not found."

        engine = BranchDiffEngine()
        result = engine.diff(branch_a, branch_b)

        lines = [
            f"Divergence point: message {result.divergence_point}",
            f"Conversation diff lines: {len(result.conversation_diff)}",
            f"Changed files: {len(result.file_diffs)}",
        ]
        for fname in sorted(result.file_diffs):
            lines.append(f"  {fname}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /loop [interval] [command]
    # ------------------------------------------------------------------

    async def loop_handler(args: str) -> str:
        from lidco.session.loop_runner import LoopRunner, LoopConfig

        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            # Show status or usage
            runner: LoopRunner | None = _state.get("loop_runner")  # type: ignore[assignment]
            if runner and runner.is_running:
                return f"Loop running: {len(runner.results())} iterations so far."
            return "Usage: /loop <interval> <command>  (e.g., /loop 5m /status)"

        interval_spec, command = parts[0], parts[1]

        try:
            seconds = LoopRunner.parse_interval(interval_spec)
        except ValueError as exc:
            return f"Invalid interval: {exc}"

        config = LoopConfig(command=command, interval_seconds=seconds, max_iterations=1)
        runner = LoopRunner(config)
        _state["loop_runner"] = runner

        # Execute once synchronously (non-blocking single iteration)
        def _exec(cmd: str) -> str:
            return f"[simulated] {cmd}"

        runner.start(_exec)
        results = runner.results()
        last = results[-1] if results else {}
        output = last.get("output", "no output")
        return f"Loop executed '{command}' (interval={interval_spec}): {output}"

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------

    registry.register(SlashCommand("fork", "Fork conversation into a new branch", fork_handler))
    registry.register(SlashCommand("branch", "Manage conversation branches", branch_handler))
    registry.register(SlashCommand("branch-diff", "Compare two branches", branch_diff_handler))
    registry.register(SlashCommand("loop", "Run a command on a recurring interval", loop_handler))
