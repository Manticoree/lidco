"""
Q98 CLI commands — /secrets, /notify, /scheduler, /data-pipeline

Registered via register_q98_commands(registry).
"""

from __future__ import annotations

import json
import shlex


def register_q98_commands(registry) -> None:
    """Register Q98 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /secrets — Obfuscated local secrets vault
    # ------------------------------------------------------------------
    async def secrets_handler(args: str) -> str:
        """
        Usage: /secrets set <key> <value>
               /secrets get <key>
               /secrets delete <key>
               /secrets list
               /secrets export
        """
        from lidco.security.secrets_manager import SecretsManager

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /secrets <subcommand>\n"
                "  set <key> <value>  store a secret\n"
                "  get <key>          retrieve a secret\n"
                "  delete <key>       delete a secret\n"
                "  list               list all secret keys\n"
                "  export             show all as KEY=VALUE\n"
                "NOTE: secrets are XOR-obfuscated, not cryptographically secure."
            )

        subcmd = parts[0].lower()
        sm = SecretsManager()

        if subcmd == "set":
            if len(parts) < 3:
                return "Error: Usage: /secrets set <key> <value>"
            key, value = parts[1], parts[2]
            try:
                sm.set(key, value)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Secret '{key}' stored."

        if subcmd == "get":
            if len(parts) < 2:
                return "Error: key required. Usage: /secrets get <key>"
            val = sm.get(parts[1])
            if val is None:
                return f"Secret '{parts[1]}' not found."
            return f"{parts[1]} = {val!r}"

        if subcmd == "delete":
            if len(parts) < 2:
                return "Error: key required. Usage: /secrets delete <key>"
            existed = sm.delete(parts[1])
            if existed:
                return f"Secret '{parts[1]}' deleted."
            return f"Secret '{parts[1]}' not found."

        if subcmd == "list":
            keys = sm.list()
            if not keys:
                return "No secrets stored."
            return "Stored secrets:\n" + "\n".join(f"  {k}" for k in keys)

        if subcmd == "export":
            env = sm.export_env()
            if not env:
                return "No secrets to export."
            return "\n".join(f"{k}={v}" for k, v in sorted(env.items()))

        return f"Unknown subcommand '{subcmd}'. Use set/get/delete/list/export."

    registry.register_async("secrets", "Manage obfuscated local secrets vault", secrets_handler)

    # ------------------------------------------------------------------
    # /notify — Multi-channel notifications
    # ------------------------------------------------------------------
    _notify_state: dict[str, object] = {}

    async def notify_handler(args: str) -> str:
        """
        Usage: /notify send <title> <body> [--level info|warning|error|success]
               /notify webhook add <url>
               /notify webhook remove <url>
               /notify history [--limit N]
               /notify clear
        """
        from lidco.notifications.center import NotificationCenter

        if "center" not in _notify_state:
            _notify_state["center"] = NotificationCenter()

        center: NotificationCenter = _notify_state["center"]  # type: ignore[assignment]

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /notify <subcommand>\n"
                "  send <title> <body> [--level info|warning|error|success]\n"
                "  webhook add <url>\n"
                "  webhook remove <url>\n"
                "  history [--limit N]\n"
                "  clear"
            )

        subcmd = parts[0].lower()

        if subcmd == "send":
            if len(parts) < 3:
                return "Error: Usage: /notify send <title> <body> [--level LEVEL]"
            title = parts[1]
            body = parts[2]
            level = "info"
            i = 3
            while i < len(parts):
                if parts[i] == "--level" and i + 1 < len(parts):
                    i += 1
                    level = parts[i]
                i += 1
            try:
                n = center.send(title, body, level=level)
            except ValueError as exc:
                return f"Error: {exc}"
            errors_note = f" (errors: {', '.join(n.errors)})" if n.errors else ""
            return f"Notification sent to channels: {n.channels}{errors_note}"

        if subcmd == "webhook":
            if len(parts) < 3:
                return "Error: Usage: /notify webhook add|remove <url>"
            action, url = parts[1].lower(), parts[2]
            if action == "add":
                center.add_webhook(url)
                return f"Webhook added: {url}"
            if action == "remove":
                removed = center.remove_webhook(url)
                return f"Webhook removed: {url}" if removed else f"Webhook not found: {url}"
            return f"Unknown webhook action '{action}'. Use add or remove."

        if subcmd == "history":
            limit = 10
            i = 1
            while i < len(parts):
                if parts[i] == "--limit" and i + 1 < len(parts):
                    i += 1
                    try:
                        limit = int(parts[i])
                    except ValueError:
                        pass
                i += 1
            history = center.get_history()[:limit]
            if not history:
                return "No notifications in history."
            lines = [
                f"[{n.level.upper()}] {n.title}: {n.body}"
                for n in history
            ]
            return f"Notification history (latest {len(lines)}):\n" + "\n".join(lines)

        if subcmd == "clear":
            count = center.clear_history()
            return f"Cleared {count} notification(s) from history."

        return f"Unknown subcommand '{subcmd}'. Use send/webhook/history/clear."

    registry.register_async("notify", "Send multi-channel notifications", notify_handler)

    # ------------------------------------------------------------------
    # /scheduler — Persistent task scheduler
    # ------------------------------------------------------------------
    async def scheduler_handler(args: str) -> str:
        """
        Usage: /scheduler add <name> <command> --schedule <schedule>
               /scheduler remove <id>
               /scheduler list
               /scheduler run
        """
        from lidco.scheduler.task_scheduler import TaskScheduler

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /scheduler <subcommand>\n"
                "  add <name> <command> --schedule <schedule>  add a task\n"
                "  remove <id>                                 remove a task\n"
                "  list                                        list all tasks\n"
                "  run                                         execute due tasks now\n"
                "Schedule formats: 'every 30s', 'every 5m', 'every 2h', ISO datetime"
            )

        subcmd = parts[0].lower()
        sched = TaskScheduler()

        if subcmd == "add":
            if len(parts) < 3:
                return "Error: Usage: /scheduler add <name> <command> --schedule <schedule>"
            name = parts[1]
            cmd = parts[2]
            schedule = ""
            i = 3
            while i < len(parts):
                if parts[i] == "--schedule" and i + 1 < len(parts):
                    i += 1
                    schedule = parts[i]
                i += 1
            if not schedule:
                return "Error: --schedule is required."
            try:
                task = sched.add(name, cmd, schedule)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Task added: {task.id[:8]}... '{task.name}' → '{task.command}' @ {task.schedule}"

        if subcmd == "remove":
            if len(parts) < 2:
                return "Error: task ID required. Usage: /scheduler remove <id>"
            removed = sched.remove(parts[1])
            return f"Task {parts[1]} removed." if removed else f"Task '{parts[1]}' not found."

        if subcmd == "list":
            tasks = sched.list()
            if not tasks:
                return "No scheduled tasks."
            lines = []
            for t in tasks:
                status = "enabled" if t.enabled else "disabled"
                lines.append(f"  {t.id[:8]}  [{status}]  {t.name}  @ {t.schedule}  runs={t.run_count}")
            return "Scheduled tasks:\n" + "\n".join(lines)

        if subcmd == "run":
            results = sched.run_due()
            if not results:
                return "No due tasks to run."
            return "\n\n".join(r.format_summary() for r in results)

        return f"Unknown subcommand '{subcmd}'. Use add/remove/list/run."

    registry.register_async("scheduler", "Manage persistent scheduled tasks", scheduler_handler)

    # ------------------------------------------------------------------
    # /data-pipeline — Composable ETL pipeline
    # ------------------------------------------------------------------
    async def data_pipeline_handler(args: str) -> str:
        """
        Usage: /data-pipeline run <json-file> [--filter <expr>] [--sort <key>]
                                              [--limit N] [--unique]
               /data-pipeline steps
        """
        from lidco.data.pipeline import DataPipeline, FilterStep, LimitStep, MapStep, SortStep, UniqueStep

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /data-pipeline <subcommand>\n"
                "  run <json-file> [--sort <key>] [--limit N] [--unique]\n"
                "     Load JSON array from file and process it.\n"
                "  steps\n"
                "     List available step types."
            )

        subcmd = parts[0].lower()

        if subcmd == "steps":
            return (
                "Available pipeline steps:\n"
                "  FilterStep(predicate)          keep items matching predicate\n"
                "  MapStep(transform)             transform each item\n"
                "  SortStep(key, reverse)         sort items by key\n"
                "  LimitStep(n)                   take first N items\n"
                "  UniqueStep(key)                deduplicate items"
            )

        if subcmd == "run":
            if len(parts) < 2:
                return "Error: JSON file path required."

            import ast
            from pathlib import Path

            file_path = parts[1]
            try:
                raw = Path(file_path).read_text(encoding="utf-8")
                data = json.loads(raw)
            except FileNotFoundError:
                return f"Error: file not found: {file_path}"
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON: {exc}"

            if not isinstance(data, list):
                return "Error: JSON file must contain a top-level array."

            pipeline = DataPipeline("cli")

            sort_key: str | None = None
            limit_n: int | None = None
            add_unique = False
            i = 2
            while i < len(parts):
                tok = parts[i]
                if tok == "--sort" and i + 1 < len(parts):
                    i += 1
                    sort_key = parts[i]
                elif tok == "--limit" and i + 1 < len(parts):
                    i += 1
                    try:
                        limit_n = int(parts[i])
                    except ValueError:
                        return f"Error: --limit must be an integer, got {parts[i]!r}"
                elif tok == "--unique":
                    add_unique = True
                i += 1

            if sort_key:
                pipeline.add_step(SortStep(key=lambda x, k=sort_key: x.get(k) if isinstance(x, dict) else x, name=f"sort({sort_key})"))
            if limit_n is not None:
                pipeline.add_step(LimitStep(limit_n))
            if add_unique:
                pipeline.add_step(UniqueStep())

            if not pipeline.steps:
                # No steps — just show summary of raw data
                return f"Loaded {len(data)} item(s). Use --sort/--limit/--unique to process."

            try:
                result = pipeline.run(data)
            except Exception as exc:
                return f"Error: {exc}"

            preview = json.dumps(result[:5], indent=2, default=str)
            more = f"\n  ... and {len(result) - 5} more" if len(result) > 5 else ""
            return f"Pipeline result: {len(result)} item(s)\n{preview}{more}"

        return f"Unknown subcommand '{subcmd}'. Use 'run' or 'steps'."

    registry.register_async("data-pipeline", "Process data with composable ETL pipeline", data_pipeline_handler)
