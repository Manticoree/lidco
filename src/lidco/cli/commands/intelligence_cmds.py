"""CLI commands for deep intelligence features (Q83)."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.cli.commands.registry import CommandRegistry


def register_intelligence_commands(registry: "CommandRegistry") -> None:
    """Register /index, /plan-validate, /autofix, /parallel commands."""

    async def index_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        parts = args.strip().split()
        save = "--save" in parts
        try:
            from lidco.indexer.codebase_indexer import CodebaseIndexer
            indexer = CodebaseIndexer(".")
            if "--load" in parts:
                loaded = indexer.load()
                if not loaded:
                    return "No cached index found. Run /index to build one."
                idx = indexer.get_index()
                return f"Loaded cached index: {len(idx)} files."
            report = indexer.build()
            if save:
                indexer.save()
            return report.format_summary()
        except Exception as e:
            return f"/index failed: {e}"

    async def plan_validate_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        plan_text = args.strip()
        if not plan_text:
            return "Usage: /plan-validate <plan text with numbered steps>"
        try:
            from lidco.agents.plan_validator import PlanValidator
            validator = PlanValidator()
            result = await validator.validate(plan_text, auto_approve=True)
            lines = [validator.format_plan(result.steps)]
            lines.append(f"\nApproved: {result.approved} ({len(result.approved_steps)}/{len(result.steps)} steps)")
            return "\n".join(lines)
        except Exception as e:
            return f"/plan-validate failed: {e}"

    async def autofix_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        parts = args.strip().split(None, 1)
        if not parts:
            return "Usage: /autofix <command> [--max N]"
        command = parts[0] if len(parts) == 1 else parts[0]
        # Parse --max N
        max_iter = 3
        tokens = args.strip().split()
        if "--max" in tokens:
            idx = tokens.index("--max")
            if idx + 1 < len(tokens):
                try:
                    max_iter = int(tokens[idx + 1])
                except ValueError:
                    pass
        # Command is everything except --max N
        cmd_parts = [t for i, t in enumerate(tokens) if t != "--max" and (i == 0 or tokens[i-1] != "--max")]
        command = " ".join(cmd_parts)
        try:
            from lidco.agents.auto_fixer import AutoFixer
            fixer = AutoFixer(max_iterations=max_iter)
            result = fixer.run_sync(command)
            status = "PASSED" if result.fixed else "FAILED"
            out = result.stdout[:500] if result.stdout else result.stderr[:500]
            return f"[{status}] {command}\n{out}"
        except Exception as e:
            return f"/autofix failed: {e}"

    async def parallel_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        """Usage: /parallel task1 | task2 | task3"""
        if not args.strip():
            return "Usage: /parallel <task1> | <task2> | ..."
        task_names = [t.strip() for t in args.split("|") if t.strip()]
        if not task_names:
            return "No tasks specified."
        try:
            from lidco.agents.worktree_runner import WorktreeRunner, WorktreeTask
            runner = WorktreeRunner(".")
            tasks = [WorktreeTask(name=t, prompt=t) for t in task_names]
            result = await runner.run_parallel(tasks)
            lines = [f"Parallel execution: {result.successful}/{len(tasks)} succeeded"]
            for r in result.results:
                icon = "✓" if r.success else "✗"
                lines.append(f"  {icon} {r.task.name}: {r.output[:80] or r.error[:80]}")
            return "\n".join(lines)
        except Exception as e:
            return f"/parallel failed: {e}"

    from lidco.cli.commands.registry import SlashCommand
    # Registered as /deep-index to avoid overriding core.py's /index (IndexDatabase-based)
    registry.register(SlashCommand("deep-index", "Build/refresh codebase index (DeepWiki-style)", index_handler))
    registry.register(SlashCommand("plan-validate", "Show plan for user review before execution", plan_validate_handler))
    registry.register(SlashCommand("autofix", "Run a command and auto-fix failures", autofix_handler))
    registry.register(SlashCommand("parallel", "Run tasks in parallel isolated worktrees", parallel_handler))
