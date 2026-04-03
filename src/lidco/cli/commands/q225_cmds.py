"""Q225 CLI commands: /jobs, /job-status, /job-recover, /job-clean."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q225 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    def _get_store():
        from lidco.jobs.persistence import JobPersistenceStore
        if "store" not in _state:
            _state["store"] = JobPersistenceStore()
        return _state["store"]

    async def jobs_handler(args: str) -> str:
        store = _get_store()
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else "list"

        if sub in ("list", ""):
            jobs = store.query(limit=20)
            if not jobs:
                return "No jobs found."
            lines = ["Jobs:"]
            for j in jobs:
                err = f" error={j.error}" if j.error else ""
                lines.append(f"  {j.id[:8]} [{j.status}] {j.name}{err}")
            return "\n".join(lines)

        if sub == "status":
            if len(parts) < 2:
                return "Usage: /jobs status <id>"
            job = store.get(parts[1])
            if job is None:
                return f"Job '{parts[1]}' not found."
            lines = [
                f"Job {job.id}",
                f"  name: {job.name}",
                f"  status: {job.status}",
                f"  payload: {job.payload}",
            ]
            if job.result:
                lines.append(f"  result: {job.result}")
            if job.error:
                lines.append(f"  error: {job.error}")
            return "\n".join(lines)

        if sub == "clean":
            import time
            hours = 24.0
            if len(parts) >= 2:
                try:
                    hours = float(parts[1])
                except ValueError:
                    return "Usage: /jobs clean <hours>"
            cutoff = time.time() - hours * 3600
            removed = store.cleanup(cutoff)
            return f"Cleaned {removed} job(s) older than {hours}h."

        return (
            "Usage: /jobs <sub>\n"
            "  list               -- list recent jobs\n"
            "  status <id>        -- job details\n"
            "  clean <hours>      -- remove old completed/failed jobs"
        )

    async def job_status_handler(args: str) -> str:
        store = _get_store()
        job_id = args.strip()
        if not job_id:
            return "Usage: /job-status <id>"
        job = store.get(job_id)
        if job is None:
            return f"Job '{job_id}' not found."
        lines = [
            f"Job {job.id}",
            f"  name: {job.name}",
            f"  status: {job.status}",
            f"  payload: {job.payload}",
        ]
        if job.result:
            lines.append(f"  result: {job.result}")
        if job.error:
            lines.append(f"  error: {job.error}")
        return "\n".join(lines)

    async def job_recover_handler(args: str) -> str:
        from lidco.jobs.recovery import JobRecovery
        store = _get_store()
        recovery = JobRecovery(store)
        sub = args.strip().lower()

        if sub == "scan" or sub == "":
            actions = recovery.scan()
            if not actions:
                return "No interrupted jobs found."
            lines = ["Recovery actions:"]
            for a in actions:
                lines.append(f"  {a.job_id[:8]} -> {a.action} ({a.reason})")
            return "\n".join(lines)

        if sub == "execute":
            result = recovery.execute()
            return (
                f"Recovery complete: "
                f"{result['resumed']} resumed, "
                f"{result['failed']} failed, "
                f"{result['skipped']} skipped."
            )

        return "Usage: /job-recover [scan | execute]"

    async def job_clean_handler(args: str) -> str:
        import time
        store = _get_store()
        hours_str = args.strip()
        if not hours_str:
            return "Usage: /job-clean <hours>"
        try:
            hours = float(hours_str)
        except ValueError:
            return "Usage: /job-clean <hours>"
        cutoff = time.time() - hours * 3600
        removed = store.cleanup(cutoff)
        return f"Cleaned {removed} job(s) older than {hours}h."

    registry.register(SlashCommand("jobs", "List/status/clean background jobs", jobs_handler))
    registry.register(SlashCommand("job-status", "Detailed job status + progress", job_status_handler))
    registry.register(SlashCommand("job-recover", "Recover interrupted jobs", job_recover_handler))
    registry.register(SlashCommand("job-clean", "Cleanup old completed/failed jobs", job_clean_handler))
