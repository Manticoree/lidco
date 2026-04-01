"""Q200 CLI commands: /task-create, /task-list, /task-status, /task-stop, /task-output."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q200 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    def _get_store():
        from lidco.tasks.store import TaskStore

        if "store" not in _state:
            _state["store"] = TaskStore()
        return _state["store"]

    # ------------------------------------------------------------------
    # /task-create
    # ------------------------------------------------------------------

    async def task_create_handler(args: str) -> str:
        from lidco.tasks.store import TaskStore

        store: TaskStore = _get_store()
        parts = args.strip().split(maxsplit=1)
        name = parts[0] if parts else ""
        if not name:
            return "Usage: /task-create <name> [description]"
        description = parts[1] if len(parts) > 1 else ""
        task = store.create(name, description=description)
        return f"Created task {task.id}: {task.name} [{task.status.value}]"

    # ------------------------------------------------------------------
    # /task-list
    # ------------------------------------------------------------------

    async def task_list_handler(args: str) -> str:
        from lidco.tasks.store import TaskStatus, TaskStore

        store: TaskStore = _get_store()
        status_filter = None
        arg = args.strip().lower()
        if arg:
            try:
                status_filter = TaskStatus(arg)
            except ValueError:
                return f"Unknown status '{arg}'. Valid: pending, running, done, failed, cancelled"

        tasks = store.list_tasks(status=status_filter)
        if not tasks:
            return "No tasks found."
        lines = [f"{len(tasks)} task(s):"]
        for t in tasks:
            lines.append(f"  [{t.id}] {t.name} — {t.status.value}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /task-status
    # ------------------------------------------------------------------

    async def task_status_handler(args: str) -> str:
        from lidco.tasks.store import TaskStore

        store: TaskStore = _get_store()
        task_id = args.strip()
        if not task_id:
            return "Usage: /task-status <task-id>"
        task = store.get(task_id)
        if task is None:
            return f"Task '{task_id}' not found."
        lines = [
            f"Task {task.id}: {task.name}",
            f"  Status: {task.status.value}",
            f"  Description: {task.description or '(none)'}",
        ]
        if task.output:
            lines.append(f"  Output: {task.output}")
        if task.error:
            lines.append(f"  Error: {task.error}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /task-stop
    # ------------------------------------------------------------------

    async def task_stop_handler(args: str) -> str:
        from lidco.tasks.store import TaskStatus, TaskStore

        store: TaskStore = _get_store()
        task_id = args.strip()
        if not task_id:
            return "Usage: /task-stop <task-id>"
        task = store.get(task_id)
        if task is None:
            return f"Task '{task_id}' not found."
        if task.status != TaskStatus.RUNNING:
            return f"Task '{task_id}' is not running (status: {task.status.value})."
        store.update_status(task_id, TaskStatus.CANCELLED)
        return f"Task '{task_id}' cancelled."

    # ------------------------------------------------------------------
    # /task-output
    # ------------------------------------------------------------------

    async def task_output_handler(args: str) -> str:
        from lidco.tasks.store import TaskStore

        store: TaskStore = _get_store()
        task_id = args.strip()
        if not task_id:
            return "Usage: /task-output <task-id>"
        task = store.get(task_id)
        if task is None:
            return f"Task '{task_id}' not found."
        if not task.output:
            return f"No output for task '{task_id}'."
        return task.output

    registry.register(SlashCommand("task-create", "Create a new task", task_create_handler))
    registry.register(SlashCommand("task-list", "List tasks", task_list_handler))
    registry.register(SlashCommand("task-status", "Show task status", task_status_handler))
    registry.register(SlashCommand("task-stop", "Stop a running task", task_stop_handler))
    registry.register(SlashCommand("task-output", "Show task output", task_output_handler))
