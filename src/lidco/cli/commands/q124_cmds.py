"""Q124 CLI commands: /run (demo | status | pipeline)."""
from __future__ import annotations

import asyncio

_state: dict = {}


def register(registry) -> None:
    """Register Q124 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def run_handler(args: str) -> str:
        from lidco.execution.concurrent_runner import ConcurrentRunner
        from lidco.execution.progress_tracker import ProgressTracker
        from lidco.execution.task_pipeline import TaskPipeline, PipelineStep

        # Lazy-init tracker
        if "tracker" not in _state:
            _state["tracker"] = ProgressTracker()

        tracker: ProgressTracker = _state["tracker"]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "demo":
            runner = ConcurrentRunner(max_concurrency=3)

            async def fast_task() -> str:
                await asyncio.sleep(0)
                return "fast done"

            async def medium_task() -> str:
                await asyncio.sleep(0)
                return "medium done"

            async def slow_task() -> str:
                await asyncio.sleep(0)
                return "slow done"

            tasks = [
                runner.make_task("fast", fast_task),
                runner.make_task("medium", medium_task),
                runner.make_task("slow", slow_task),
            ]

            # Track in progress tracker
            for t in tasks:
                tracker.start(t.id, t.name)

            report = await runner.run_all(tasks)

            for outcome in report.outcomes:
                tracker.finish(outcome.id, success=outcome.success)

            _state["last_report"] = report

            lines = [
                f"Ran {len(report.outcomes)} tasks: {report.succeeded} succeeded, {report.failed} failed.",
                f"Success rate: {report.success_rate:.0%}",
                f"Total elapsed: {report.total_elapsed:.3f}s",
            ]
            for o in report.outcomes:
                status = f"ok ({o.result})" if o.success else f"FAIL: {o.error}"
                lines.append(f"  [{o.name}] {status}")
            return "\n".join(lines)

        if sub == "status":
            summary = tracker.summary()
            lines = ["Progress tracker summary:"]
            for k, v in summary.items():
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)

        if sub == "pipeline":
            pipeline = TaskPipeline()
            pipeline.add_step(PipelineStep("upper", lambda s: s.upper() if isinstance(s, str) else str(s)))
            pipeline.add_step(PipelineStep("strip", lambda s: s.strip()))
            pipeline.add_step(PipelineStep("count_words", lambda s: f"{s} [{len(s.split())} words]"))

            result = await pipeline.run_async("  hello world from lidco  ")
            lines = [
                f"Pipeline result: {result.final_output}",
                f"Steps run: {result.steps_run}, skipped: {result.steps_skipped}",
                f"Success: {result.success}",
            ]
            if result.errors:
                for name, err in result.errors.items():
                    lines.append(f"  Error in {name}: {err}")
            return "\n".join(lines)

        return (
            "Usage: /run <sub>\n"
            "  demo      -- run 3 fake tasks concurrently\n"
            "  status    -- show progress tracker summary\n"
            "  pipeline  -- run a demo 3-step pipeline"
        )

    registry.register(SlashCommand("run", "Async concurrent runner demo (Q124)", run_handler))
