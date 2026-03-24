"""Slash commands for pipeline and scheduler management."""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Module-level state
_last_results: list = []
_cron_runner: Any = None  # lazy init


def _get_cron_runner() -> Any:
    global _cron_runner
    if _cron_runner is None:
        try:
            from lidco.scheduler.cron_runner import CronRunner
            _cron_runner = CronRunner()
        except Exception:
            _cron_runner = None
    return _cron_runner


# ------------------------------------------------------------------
# /pipeline handlers
# ------------------------------------------------------------------

async def pipeline_run_handler(args: str = "") -> str:
    """/pipeline run — poll GitHub Issues and run the IssueToPRPipeline."""
    global _last_results
    try:
        from lidco.pipelines.issue_to_pr import IssueToPRPipeline, PipelineConfig
        config = PipelineConfig(project_dir=Path.cwd())
        pipeline = IssueToPRPipeline(config=config)
        results = pipeline.poll_and_run()
        _last_results = list(results)
        if not results:
            return "Pipeline run complete. No new issues found."
        lines = [f"Pipeline processed {len(results)} issue(s):"]
        for r in results:
            lines.append(f"  #{r.issue_number}: {r.status} (branch: {r.branch})")
        return "\n".join(lines)
    except Exception as exc:
        return f"Pipeline run failed: {exc}"


async def pipeline_status_handler(args: str = "") -> str:
    """/pipeline status — show last pipeline run results."""
    if not _last_results:
        return "No pipeline results yet. Run `/pipeline run` first."
    lines = [f"Last pipeline run — {len(_last_results)} result(s):"]
    for r in _last_results:
        lines.append(
            f"  #{r.issue_number}: {r.status} | security={r.security_passed}"
            f" | branch={r.branch}"
        )
    return "\n".join(lines)


# ------------------------------------------------------------------
# /schedule handlers
# ------------------------------------------------------------------

async def schedule_add_handler(args: str = "") -> str:
    """/schedule add <name> "<cron>" <instruction> — register a cron task."""
    # Parse: name "cron expr" instruction
    import shlex
    try:
        tokens = shlex.split(args.strip())
    except ValueError as exc:
        return f"Parse error: {exc}"

    if len(tokens) < 3:
        return 'Usage: /schedule add <name> "<cron 5 fields>" <instruction>'

    name = tokens[0]
    cron_expr = tokens[1]
    instruction = " ".join(tokens[2:])

    runner = _get_cron_runner()
    if runner is None:
        return "Scheduler unavailable."
    try:
        runner.add_task(name, cron_expr, instruction)
        return f"Task '{name}' added with cron '{cron_expr}'."
    except Exception as exc:
        return f"Failed to add task: {exc}"


async def schedule_remove_handler(args: str = "") -> str:
    """/schedule remove <name> — unregister a cron task."""
    name = args.strip()
    if not name:
        return "Usage: /schedule remove <name>"
    runner = _get_cron_runner()
    if runner is None:
        return "Scheduler unavailable."
    removed = runner.remove_task(name)
    if removed:
        return f"Task '{name}' removed."
    return f"Task '{name}' not found."


async def schedule_list_handler(args: str = "") -> str:
    """/schedule list — list all scheduled tasks."""
    runner = _get_cron_runner()
    if runner is None:
        return "Scheduler unavailable."
    tasks = runner.list_tasks()
    if not tasks:
        return "No scheduled tasks."
    lines = ["Scheduled tasks:"]
    for t in tasks:
        status = "enabled" if t.enabled else "disabled"
        lines.append(f"  {t.name} [{status}] cron={t.cron_expr!r}: {t.instruction}")
    return "\n".join(lines)


async def schedule_tick_handler(args: str = "") -> str:
    """/schedule tick — manually trigger a scheduler tick."""
    runner = _get_cron_runner()
    if runner is None:
        return "Scheduler unavailable."
    try:
        results = runner.tick()
        if not results:
            return "Tick complete. No tasks were due."
        lines = [f"Tick ran {len(results)} task(s):"]
        for r in results:
            status = "ok" if r.success else f"error: {r.error}"
            lines.append(f"  {r.task_name}: {status}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Tick failed: {exc}"


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register_pipeline_commands(registry: Any) -> None:
    """Register /pipeline and /schedule slash commands."""
    from lidco.cli.commands.registry import SlashCommand

    registry.register(SlashCommand(
        "pipeline run",
        "Poll GitHub Issues and run the IssueToPRPipeline",
        pipeline_run_handler,
    ))
    registry.register(SlashCommand(
        "pipeline status",
        "Show last pipeline run results",
        pipeline_status_handler,
    ))
    registry.register(SlashCommand(
        "schedule add",
        "Add a cron-scheduled task: /schedule add <name> \"<cron>\" <instruction>",
        schedule_add_handler,
    ))
    registry.register(SlashCommand(
        "schedule remove",
        "Remove a scheduled task by name",
        schedule_remove_handler,
    ))
    registry.register(SlashCommand(
        "schedule list",
        "List all scheduled tasks",
        schedule_list_handler,
    ))
    registry.register(SlashCommand(
        "schedule tick",
        "Manually trigger a scheduler tick",
        schedule_tick_handler,
    ))
