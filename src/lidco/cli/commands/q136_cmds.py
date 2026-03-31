"""Q136 CLI commands: /schedule."""
from __future__ import annotations

import json
import time

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q136 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def schedule_handler(args: str) -> str:
        from lidco.scheduling.priority_scheduler import PriorityScheduler
        from lidco.scheduling.dependency_resolver import DependencyResolver
        from lidco.scheduling.deadline_tracker import DeadlineTracker
        from lidco.scheduling.batch_grouper import BatchGrouper

        if "priority" not in _state:
            _state["priority"] = PriorityScheduler()
        if "deps" not in _state:
            _state["deps"] = DependencyResolver()
        if "deadline" not in _state:
            _state["deadline"] = DeadlineTracker()
        if "batch" not in _state:
            _state["batch"] = BatchGrouper()

        ps: PriorityScheduler = _state["priority"]  # type: ignore[assignment]
        dr: DependencyResolver = _state["deps"]  # type: ignore[assignment]
        dt: DeadlineTracker = _state["deadline"]  # type: ignore[assignment]
        bg: BatchGrouper = _state["batch"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        # ---- priority ----
        if sub == "priority":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            detail = sub_parts[1] if len(sub_parts) > 1 else ""

            if action == "add":
                try:
                    data = json.loads(detail)
                except (json.JSONDecodeError, TypeError):
                    return "Usage: /schedule priority add {\"name\":..., \"priority\":..., \"category\":...}"
                task = ps.schedule(
                    name=data.get("name", "unnamed"),
                    priority=data.get("priority", 0),
                    category=data.get("category", "default"),
                    payload=data.get("payload"),
                )
                return f"Scheduled task {task.id[:8]} (priority={task.priority})."

            if action == "next":
                task = ps.next()
                if task is None:
                    return "No tasks in queue."
                return f"Next: {task.name} [priority={task.priority}, category={task.category}]"

            if action == "peek":
                task = ps.peek()
                if task is None:
                    return "Queue is empty."
                return f"Peek: {task.name} [priority={task.priority}]"

            if action == "list":
                cat = detail or "default"
                tasks = ps.list_by_category(cat)
                if not tasks:
                    return f"No tasks in category '{cat}'."
                lines = [f"Tasks in '{cat}':"]
                for t in tasks:
                    lines.append(f"  {t.id[:8]} {t.name} p={t.priority}")
                return "\n".join(lines)

            if action == "size":
                return f"Queue size: {ps.size}"

            return f"Priority queue size: {ps.size}"

        # ---- deps ----
        if sub == "deps":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            detail = sub_parts[1] if len(sub_parts) > 1 else ""

            if action == "add":
                try:
                    data = json.loads(detail)
                except (json.JSONDecodeError, TypeError):
                    return "Usage: /schedule deps add {\"task_id\":..., \"depends_on\":[...]}"
                dr.add_task(data["task_id"], data.get("depends_on"))
                return f"Added task '{data['task_id']}'."

            if action == "resolve":
                result = dr.resolve()
                return json.dumps({"order": result.order, "has_cycle": result.has_cycle, "cycle_path": result.cycle_path}, indent=2)

            if action == "ready":
                ready = dr.get_ready()
                return f"Ready tasks: {ready}"

            if action == "done":
                tid = detail.strip()
                if not tid:
                    return "Usage: /schedule deps done <task_id>"
                dr.mark_done(tid)
                return f"Marked '{tid}' done."

            return "Usage: /schedule deps add|resolve|ready|done"

        # ---- deadline ----
        if sub == "deadline":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            detail = sub_parts[1] if len(sub_parts) > 1 else ""

            if action == "add":
                try:
                    data = json.loads(detail)
                except (json.JSONDecodeError, TypeError):
                    return "Usage: /schedule deadline add {\"task_id\":..., \"name\":..., \"due_at\":...}"
                dl = dt.add(data["task_id"], data.get("name", ""), data["due_at"])
                return f"Deadline added: {dl.task_id} due at {dl.due_at}."

            if action == "complete":
                tid = detail.strip()
                ok = dt.complete(tid)
                return f"Completed: {ok}"

            if action == "overdue":
                items = dt.overdue()
                if not items:
                    return "No overdue deadlines."
                lines = [f"Overdue ({len(items)}):"]
                for d in items:
                    lines.append(f"  {d.task_id}: {d.name}")
                return "\n".join(lines)

            if action == "summary":
                return json.dumps(dt.summary(), indent=2)

            return json.dumps(dt.summary(), indent=2)

        # ---- batch ----
        if sub == "batch":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            detail = sub_parts[1] if len(sub_parts) > 1 else ""

            if action == "add":
                try:
                    data = json.loads(detail)
                except (json.JSONDecodeError, TypeError):
                    return "Usage: /schedule batch add {\"item\":..., \"group_key\":...}"
                result = bg.add(data.get("item"), data.get("group_key", "default"))
                if result is not None:
                    return f"Batch emitted: {result.id[:8]} ({len(result.items)} items)."
                return f"Item added. Pending: {bg.pending_count()}."

            if action == "flush":
                key = detail.strip() or None
                batches = bg.flush(key)
                if not batches:
                    return "Nothing to flush."
                return f"Flushed {len(batches)} batch(es), {sum(len(b.items) for b in batches)} items."

            if action == "stats":
                return json.dumps(bg.stats(), indent=2)

            if action == "pending":
                return f"Pending items: {bg.pending_count()}"

            return json.dumps(bg.stats(), indent=2)

        return "Usage: /schedule priority|deps|deadline|batch"

    registry.register(SlashCommand("schedule", "Task scheduling & queuing", schedule_handler))
