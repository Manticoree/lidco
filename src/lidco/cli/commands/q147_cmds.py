"""Q147 CLI commands: /notify, /toast, /alert."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q147 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ /notify

    async def notify_handler(args: str) -> str:
        from lidco.alerts.notification_queue import NotificationQueue
        from lidco.alerts.notification_history import NotificationHistory

        if "queue" not in _state:
            _state["queue"] = NotificationQueue()
        if "history" not in _state:
            _state["history"] = NotificationHistory()

        queue: NotificationQueue = _state["queue"]  # type: ignore[assignment]
        history: NotificationHistory = _state["history"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "push":
            # /notify push <level> <title> | <message>
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /notify push <level> <title> | <message>"
            level = tokens[0]
            remainder = tokens[1]
            if "|" in remainder:
                title, message = remainder.split("|", 1)
                title = title.strip()
                message = message.strip()
            else:
                title = remainder
                message = ""
            try:
                n = queue.push(level, title, message)
            except ValueError as exc:
                return str(exc)
            history.record(n)
            return f"Notification pushed: [{n.level.upper()}] {n.title}"

        if sub == "list":
            if queue.total_count == 0:
                return "No notifications."
            lines = [f"Notifications ({queue.unread_count} unread / {queue.total_count} total):"]
            for n in queue.by_level("error") + queue.by_level("warning") + queue.by_level("info") + queue.by_level("success"):
                status = " " if n.read else "*"
                lines.append(f"  {status} [{n.level.upper()}] {n.title}")
            return "\n".join(lines)

        if sub == "read":
            n = queue.pop()
            if n is None:
                return "No unread notifications."
            return f"[{n.level.upper()}] {n.title}: {n.message}"

        if sub == "clear":
            queue.clear_read()
            return "Read notifications cleared."

        return (
            "Usage: /notify <sub>\n"
            "  push <level> <title> | <message>  -- push notification\n"
            "  list                                -- list all\n"
            "  read                                -- pop oldest unread\n"
            "  clear                               -- clear read"
        )

    # ------------------------------------------------------------------ /toast

    async def toast_handler(args: str) -> str:
        from lidco.alerts.toast_manager import ToastManager

        if "toast" not in _state:
            _state["toast"] = ToastManager()

        mgr: ToastManager = _state["toast"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "show":
            if not rest:
                return "Usage: /toast show <message>"
            mgr.expire_old()
            t = mgr.show(rest)
            return mgr.render(t)

        if sub == "active":
            mgr.expire_old()
            active = mgr.active()
            if not active:
                return "No active toasts."
            lines = [f"Active toasts ({len(active)}):"]
            for t in active:
                lines.append(f"  {mgr.render(t)}")
            return "\n".join(lines)

        if sub == "dismiss":
            if rest:
                try:
                    idx = int(rest)
                except ValueError:
                    return "Usage: /toast dismiss <index>"
                if mgr.dismiss(idx):
                    return f"Toast {idx} dismissed."
                return f"No active toast at index {idx}."
            else:
                mgr.dismiss_all()
                return "All toasts dismissed."

        return (
            "Usage: /toast <sub>\n"
            "  show <message>    -- show toast\n"
            "  active            -- list active toasts\n"
            "  dismiss [index]   -- dismiss one or all"
        )

    # ------------------------------------------------------------------ /alert

    async def alert_handler(args: str) -> str:
        from lidco.alerts.alert_rule import AlertRuleEngine

        if "alert" not in _state:
            _state["alert"] = AlertRuleEngine()

        engine: AlertRuleEngine = _state["alert"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "add":
            # /alert add <name> <action> <template>
            tokens = rest.split(maxsplit=2)
            if len(tokens) < 3:
                return "Usage: /alert add <name> <action> <message_template>"
            name, action, template = tokens
            # Default condition: always true
            engine.add_rule(name, lambda ctx: True, action, template)
            return f"Rule '{name}' added (action={action})."

        if sub == "list":
            rules = engine.list_rules()
            if not rules:
                return "No alert rules."
            lines = [f"Alert rules ({len(rules)}):"]
            for r in rules:
                status = "on" if r.enabled else "off"
                lines.append(f"  [{status}] {r.name} -> {r.action}: {r.message_template}")
            return "\n".join(lines)

        if sub == "eval":
            if rest:
                try:
                    ctx = json.loads(rest)
                except json.JSONDecodeError:
                    return "Invalid JSON context."
            else:
                ctx = {}
            triggered = engine.evaluate(ctx)
            if not triggered:
                return "No rules triggered."
            lines = [f"Triggered ({len(triggered)}):"]
            for rule, msg in triggered:
                lines.append(f"  [{rule.action.upper()}] {rule.name}: {msg}")
            return "\n".join(lines)

        return (
            "Usage: /alert <sub>\n"
            "  add <name> <action> <template>  -- add rule\n"
            "  list                              -- list rules\n"
            "  eval [json_context]               -- evaluate rules"
        )

    registry.register(SlashCommand("notify", "Notification queue management (Q147)", notify_handler))
    registry.register(SlashCommand("toast", "Toast messages (Q147)", toast_handler))
    registry.register(SlashCommand("alert", "Alert rules engine (Q147)", alert_handler))
