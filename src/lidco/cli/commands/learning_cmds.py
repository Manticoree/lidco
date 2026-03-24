"""CLI commands for session intelligence and learning (Q84)."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.cli.commands.registry import CommandRegistry


def register_learning_commands(registry: "CommandRegistry") -> None:
    """Register /patterns, /apply-review, /workers, /pin-session commands."""

    async def patterns_handler(args: str) -> str:
        parts = args.strip().split()
        from_diff = "--diff" in parts
        try:
            from lidco.learning.pattern_extractor import PatternExtractor
            extractor = PatternExtractor()
            if from_diff:
                import subprocess
                r = subprocess.run(["git", "diff", "HEAD"], capture_output=True, text=True, timeout=10)
                diff = r.stdout or ""
                result = extractor.extract_from_diff(diff)
            else:
                # Use last message as a code sample
                sample = registry.last_message or ""
                result = extractor.extract([{"content": sample, "role": "user"}])
            return result.format_summary()
        except Exception as e:
            return f"/patterns failed: {e}"

    async def apply_review_handler(args: str) -> str:
        review_text = args.strip()
        if not review_text:
            return "Usage: /apply-review <review text with ```suggestion blocks>"
        try:
            from lidco.review.suggestion_applier import SuggestionApplier
            applier = SuggestionApplier(".")
            suggestions = applier.parse_suggestions(review_text)
            if not suggestions:
                return "No ```suggestion blocks found in review text."
            batch = applier.apply_all(suggestions, dry_run="--dry-run" in review_text)
            return batch.format_summary()
        except Exception as e:
            return f"/apply-review failed: {e}"

    async def workers_handler(args: str) -> str:
        """Run simple tasks in parallel: /workers <task1> | <task2>"""
        if not args.strip():
            return "Usage: /workers <task1> | <task2> | ..."
        task_names = [t.strip() for t in args.split("|") if t.strip()]
        if not task_names:
            return "No tasks specified."
        try:
            from lidco.agents.worker_pool import WorkerPool, WorkItem

            async def _noop(name: str) -> str:
                return f"task '{name}' completed"

            pool = WorkerPool(max_workers=4)
            items = [WorkItem(name=t, coro=_noop(t)) for t in task_names]
            result = await pool.run_all(items)
            return result.format_summary()
        except Exception as e:
            return f"/workers failed: {e}"

    async def pin_session_handler(args: str) -> str:
        parts = args.strip().split(None, 1)
        sub = parts[0] if parts else "status"
        value = parts[1] if len(parts) > 1 else ""
        try:
            from lidco.context.session_pinning import SessionPinner
            pinner = SessionPinner(".")
            if sub == "pin" and value:
                item = pinner.pin(value)
                return f"Pinned: {item.content}"
            elif sub == "unpin" and value:
                removed = pinner.unpin(value)
                return f"Unpinned: {value}" if removed else f"Not found: {value}"
            elif sub == "list" or sub == "status":
                report = pinner.get_report()
                return report.format_summary()
            elif sub == "auto":
                # Auto-pin from last message
                sample = [{"content": registry.last_message}] if registry.last_message else []
                count = pinner.auto_pin_from_session(sample)
                return f"Auto-pinned {count} item(s) from session."
            else:
                return "Usage: /pin-session [pin <text>|unpin <text>|list|auto]"
        except Exception as e:
            return f"/pin-session failed: {e}"

    from lidco.cli.commands.registry import SlashCommand
    registry.register(SlashCommand("patterns", "Extract coding patterns from session history", patterns_handler))
    registry.register(SlashCommand("apply-review", "Auto-apply PR review suggestions", apply_review_handler))
    registry.register(SlashCommand("workers", "Run tasks in parallel worker pool", workers_handler))
    registry.register(SlashCommand("pin-session", "Pin important context for future sessions", pin_session_handler))
