"""
Q99 CLI commands — /rate-limiter, /circuit-breaker, /events, /jobs

Registered via register_q99_commands(registry).
"""
from __future__ import annotations

import json
import shlex


def register_q99_commands(registry) -> None:
    """Register Q99 slash commands onto the given registry."""

    # Shared state across handler invocations (module-level singletons)
    _rl_state: dict[str, object] = {}
    _cb_state: dict[str, object] = {}
    _eb_state: dict[str, object] = {}
    _jq_state: dict[str, object] = {}

    # ------------------------------------------------------------------
    # /rate-limiter
    # ------------------------------------------------------------------
    async def rate_limiter_handler(args: str) -> str:
        """
        Usage: /rate-limiter test
               /rate-limiter status
               /rate-limiter reset
        """
        from lidco.core.rate_limiter import RateLimiter

        if "limiter" not in _rl_state:
            _rl_state["limiter"] = RateLimiter(rate=5.0, capacity=10.0)

        limiter: RateLimiter = _rl_state["limiter"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else ""

        if not subcmd:
            return (
                "Usage: /rate-limiter <subcommand>\n"
                "  test    acquire 3 tokens and show stats\n"
                "  status  show available tokens\n"
                "  reset   restore to full capacity"
            )

        if subcmd == "test":
            results = []
            for i in range(3):
                ok = limiter.acquire(1)
                results.append(f"  acquire({i+1}): {'✓' if ok else '✗'}")
            s = limiter.stats()
            results.append(
                f"Stats: acquired={s.total_acquired}, rejected={s.total_rejected}, available={s.available_tokens:.2f}"
            )
            return "Rate limiter test:\n" + "\n".join(results)

        if subcmd == "status":
            return f"Available tokens: {limiter.available_tokens:.2f} / {limiter.capacity}"

        if subcmd == "reset":
            limiter.reset()
            return f"Rate limiter reset. Available tokens: {limiter.available_tokens:.2f}"

        return f"Unknown subcommand '{subcmd}'. Use test/status/reset."

    registry.register_async("rate-limiter", "Token bucket rate limiter", rate_limiter_handler)

    # ------------------------------------------------------------------
    # /circuit-breaker
    # ------------------------------------------------------------------
    async def circuit_breaker_handler(args: str) -> str:
        """
        Usage: /circuit-breaker test
               /circuit-breaker status
               /circuit-breaker reset
        """
        from lidco.core.circuit_breaker import CircuitBreaker

        if "breaker" not in _cb_state:
            _cb_state["breaker"] = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)

        breaker: CircuitBreaker = _cb_state["breaker"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else ""

        if not subcmd:
            return (
                "Usage: /circuit-breaker <subcommand>\n"
                "  test    make 3 successful calls and show state\n"
                "  status  show current state and stats\n"
                "  reset   force state back to CLOSED"
            )

        if subcmd == "test":
            results = []
            for i in range(3):
                try:
                    result = breaker.call(lambda: "ok")
                    results.append(f"  call({i+1}): {result}")
                except Exception as exc:
                    results.append(f"  call({i+1}): ERROR {exc}")
            s = breaker.stats()
            results.append(f"State: {s.state.value}  failures={s.failure_count}  total={s.total_calls}")
            return "Circuit breaker test:\n" + "\n".join(results)

        if subcmd == "status":
            s = breaker.stats()
            return (
                f"State: {s.state.value}\n"
                f"Failure count: {s.failure_count}\n"
                f"Total calls: {s.total_calls}  Total failures: {s.total_failures}"
            )

        if subcmd == "reset":
            breaker.reset()
            return f"Circuit breaker reset. State: {breaker.state.value}"

        return f"Unknown subcommand '{subcmd}'. Use test/status/reset."

    registry.register_async("circuit-breaker", "Circuit breaker pattern", circuit_breaker_handler)

    # ------------------------------------------------------------------
    # /events
    # ------------------------------------------------------------------
    async def events_handler(args: str) -> str:
        """
        Usage: /events publish <type> [json_data]
               /events history [type] [--limit N]
               /events clear
               /events subscribers
        """
        from lidco.events.bus import EventBus

        if "bus" not in _eb_state:
            _eb_state["bus"] = EventBus()

        bus: EventBus = _eb_state["bus"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else ""

        if not subcmd:
            return (
                "Usage: /events <subcommand>\n"
                "  publish <type> [json_data]  publish an event\n"
                "  history [type] [--limit N]  show event history\n"
                "  clear                       clear history\n"
                "  subscribers                 show subscription count"
            )

        if subcmd == "publish":
            if len(parts) < 2:
                return "Error: event type required. Usage: /events publish <type> [json_data]"
            event_type = parts[1]
            data = {}
            if len(parts) > 2:
                try:
                    data = json.loads(parts[2])
                except json.JSONDecodeError:
                    data = {"raw": parts[2]}
            event = bus.publish(event_type, data)
            return f"Event published: type={event_type} id={event.id[:8]}..."

        if subcmd == "history":
            event_type = None
            limit = 10
            i = 1
            while i < len(parts):
                if parts[i] == "--limit" and i + 1 < len(parts):
                    i += 1
                    try:
                        limit = int(parts[i])
                    except ValueError:
                        pass
                elif not parts[i].startswith("--"):
                    event_type = parts[i]
                i += 1
            events = bus.get_history(event_type=event_type, limit=limit)
            if not events:
                return "No events in history."
            lines = [f"  [{e.type}] id={e.id[:8]} data={e.data}" for e in events]
            return f"Event history ({len(lines)}):\n" + "\n".join(lines)

        if subcmd == "clear":
            count = bus.clear_history()
            return f"Cleared {count} event(s) from history."

        if subcmd == "subscribers":
            return f"Total subscriptions: {bus.subscriber_count}"

        return f"Unknown subcommand '{subcmd}'. Use publish/history/clear/subscribers."

    registry.register_async("events", "Publish-subscribe event bus", events_handler)

    # ------------------------------------------------------------------
    # /jobs
    # ------------------------------------------------------------------
    async def jobs_handler(args: str) -> str:
        """
        Usage: /jobs submit <name> [--priority N]
               /jobs list [--status STATUS]
               /jobs status <id>
               /jobs cancel <id>
               /jobs start
               /jobs stop
        """
        from lidco.execution.job_queue import JobQueue, JobStatus

        if "queue" not in _jq_state:
            _jq_state["queue"] = JobQueue()

        jq: JobQueue = _jq_state["queue"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else ""

        if not subcmd:
            return (
                "Usage: /jobs <subcommand>\n"
                "  submit <name> [--priority N]  submit a demo job\n"
                "  list [--status STATUS]         list jobs\n"
                "  status <id>                    show job details\n"
                "  cancel <id>                    cancel pending job\n"
                "  start [--workers N]            start worker threads\n"
                "  stop                           stop workers"
            )

        if subcmd == "submit":
            if len(parts) < 2:
                return "Error: name required. Usage: /jobs submit <name> [--priority N]"
            name = parts[1]
            priority = 0
            i = 2
            while i < len(parts):
                if parts[i] == "--priority" and i + 1 < len(parts):
                    i += 1
                    try:
                        priority = int(parts[i])
                    except ValueError:
                        pass
                i += 1
            import time as _time
            job = jq.submit(name, lambda: f"done:{name}", priority=priority)
            return f"Job submitted: {job.id[:8]}... '{job.name}' priority={job.priority}"

        if subcmd == "list":
            status_filter = None
            i = 1
            while i < len(parts):
                if parts[i] == "--status" and i + 1 < len(parts):
                    i += 1
                    try:
                        status_filter = JobStatus(parts[i].lower())
                    except ValueError:
                        return f"Error: unknown status '{parts[i]}'"
                i += 1
            jobs = jq.list_jobs(status=status_filter)
            if not jobs:
                return "No jobs."
            lines = [
                f"  {j.id[:8]}  [{j.status.value}]  p={j.priority}  {j.name}"
                for j in jobs
            ]
            return f"Jobs ({len(lines)}):\n" + "\n".join(lines)

        if subcmd == "status":
            if len(parts) < 2:
                return "Error: job ID required."
            job = jq.get_job(parts[1])
            if job is None:
                # Try prefix match
                all_jobs = jq.list_jobs()
                matches = [j for j in all_jobs if j.id.startswith(parts[1])]
                job = matches[0] if len(matches) == 1 else None
            if job is None:
                return f"Job '{parts[1]}' not found."
            result_str = ""
            if job.result:
                result_str = f"\n  result: {job.result.result}  error: {job.result.error or 'none'}"
            return (
                f"Job: {job.id[:8]}\n"
                f"  name: {job.name}  status: {job.status.value}  priority: {job.priority}"
                + result_str
            )

        if subcmd == "cancel":
            if len(parts) < 2:
                return "Error: job ID required."
            cancelled = jq.cancel(parts[1])
            return f"Job {parts[1][:8]} cancelled." if cancelled else f"Cannot cancel '{parts[1]}' (not pending or not found)."

        if subcmd == "start":
            workers = 2
            i = 1
            while i < len(parts):
                if parts[i] == "--workers" and i + 1 < len(parts):
                    i += 1
                    try:
                        workers = int(parts[i])
                    except ValueError:
                        pass
                i += 1
            jq.start(workers=workers)
            return f"Job queue started with {workers} worker(s)."

        if subcmd == "stop":
            jq.stop()
            return "Job queue stopped."

        return f"Unknown subcommand '{subcmd}'. Use submit/list/status/cancel/start/stop."

    registry.register_async("jobs", "Priority job queue with worker threads", jobs_handler)
