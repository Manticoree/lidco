"""Q201 CLI commands: /cron-create, /cron-list, /cron-delete, /cron-run."""

from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q201 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /cron-create
    # ------------------------------------------------------------------

    async def cron_create_handler(args: str) -> str:
        from lidco.cron.scheduler import CronScheduler
        from lidco.cron.parser import CronParseError

        if "scheduler" not in _state:
            _state["scheduler"] = CronScheduler()
        sched: CronScheduler = _state["scheduler"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /cron-create <expression> <name>"

        # Expression might be quoted or first 5 space-separated tokens
        tokens = args.strip().split()
        if len(tokens) < 6:
            return "Usage: /cron-create <min> <hour> <dom> <mon> <dow> <name>"

        expression = " ".join(tokens[:5])
        name = " ".join(tokens[5:])

        try:
            job = sched.add_job(name, expression)
        except CronParseError as exc:
            return f"Error: {exc}"

        return f"Created job '{job.name}' (id={job.id}) with schedule '{expression}'."

    # ------------------------------------------------------------------
    # /cron-list
    # ------------------------------------------------------------------

    async def cron_list_handler(args: str) -> str:
        from lidco.cron.scheduler import CronScheduler

        if "scheduler" not in _state:
            _state["scheduler"] = CronScheduler()
        sched: CronScheduler = _state["scheduler"]  # type: ignore[assignment]

        jobs = sched.list_jobs()
        if not jobs:
            return "No scheduled jobs."

        lines = [f"{len(jobs)} job(s):"]
        for j in jobs:
            lines.append(f"  [{j.status.value}] {j.name} — {j.expression} (id={j.id})")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /cron-delete
    # ------------------------------------------------------------------

    async def cron_delete_handler(args: str) -> str:
        from lidco.cron.scheduler import CronScheduler

        if "scheduler" not in _state:
            _state["scheduler"] = CronScheduler()
        sched: CronScheduler = _state["scheduler"]  # type: ignore[assignment]

        job_id = args.strip()
        if not job_id:
            return "Usage: /cron-delete <job-id>"

        removed = sched.remove_job(job_id)
        if not removed:
            return f"Job '{job_id}' not found."
        return f"Deleted job '{job_id}'."

    # ------------------------------------------------------------------
    # /cron-run
    # ------------------------------------------------------------------

    async def cron_run_handler(args: str) -> str:
        from lidco.cron.scheduler import CronScheduler
        from lidco.cron.executor import CronExecutor

        if "scheduler" not in _state:
            _state["scheduler"] = CronScheduler()
        if "executor" not in _state:
            _state["executor"] = CronExecutor()
        sched: CronScheduler = _state["scheduler"]  # type: ignore[assignment]
        executor: CronExecutor = _state["executor"]  # type: ignore[assignment]

        job_id = args.strip()
        if not job_id:
            return "Usage: /cron-run <job-id>"

        job = sched.get_job(job_id)
        if job is None:
            return f"Job '{job_id}' not found."

        result = executor.execute(job, lambda: f"Executed {job.name}")
        sched.mark_run(job_id, result.success)
        status = "success" if result.success else "failed"
        return f"Job '{job.name}' executed: {status} ({result.duration_ms:.1f}ms)"

    registry.register(SlashCommand("cron-create", "Create a cron job", cron_create_handler))
    registry.register(SlashCommand("cron-list", "List cron jobs", cron_list_handler))
    registry.register(SlashCommand("cron-delete", "Delete a cron job", cron_delete_handler))
    registry.register(SlashCommand("cron-run", "Run a cron job now", cron_run_handler))
