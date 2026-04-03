"""Q270 CLI commands: /notify, /sound, /notify-rules, /notify-history."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q270 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /notify
    # ------------------------------------------------------------------

    async def notify_handler(args: str) -> str:
        from lidco.notify.dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "send":
            tokens = rest.split(maxsplit=2)
            if len(tokens) < 2:
                return "Usage: /notify send <title> <message> [level]"
            title = tokens[0]
            message = tokens[1] if len(tokens) >= 2 else ""
            level = tokens[2] if len(tokens) >= 3 else "info"
            n = dispatcher.send(title, message, level)
            return f"Notification sent: {n.title} ({n.level}) delivered={n.delivered}"
        if sub == "enable":
            dispatcher.enable()
            return "Notifications enabled."
        if sub == "disable":
            dispatcher.disable()
            return "Notifications disabled."
        if sub == "history":
            entries = dispatcher.history()
            if not entries:
                return "No notification history."
            lines = [f"  {n.id}: [{n.level}] {n.title}" for n in entries]
            return "Notification history:\n" + "\n".join(lines)
        return "Usage: /notify [send <title> <message> [level] | enable | disable | history]"

    # ------------------------------------------------------------------
    # /sound
    # ------------------------------------------------------------------

    async def sound_handler(args: str) -> str:
        from lidco.notify.sound import SoundEngine

        engine = SoundEngine()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "play":
            if not rest:
                return "Usage: /sound play <event>"
            ev = engine.play(rest)
            return f"Played sound: {ev.name}"
        if sub == "mute":
            engine.mute()
            return "Sound muted."
        if sub == "unmute":
            engine.unmute()
            return "Sound unmuted."
        if sub == "register":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /sound register <event> <file>"
            engine.register_sound(tokens[0], tokens[1])
            return f"Registered sound: {tokens[0]} -> {tokens[1]}"
        if sub == "list":
            events = engine.available_events()
            return "Available sound events: " + ", ".join(events)
        return "Usage: /sound [play <event> | mute | unmute | register <event> <file> | list]"

    # ------------------------------------------------------------------
    # /notify-rules
    # ------------------------------------------------------------------

    async def notify_rules_handler(args: str) -> str:
        from lidco.notify.rules import NotificationRules, NotifyRule

        rules = NotificationRules()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /notify-rules add <name> <event>"
            rule = rules.add_rule(NotifyRule(name=tokens[0], event=tokens[1]))
            return f"Rule added: {rule.name} -> {rule.event}"
        if sub == "remove":
            if not rest:
                return "Usage: /notify-rules remove <name>"
            ok = rules.remove_rule(rest)
            return f"Rule removed: {rest}" if ok else f"Rule not found: {rest}"
        if sub == "enable":
            if not rest:
                return "Usage: /notify-rules enable <name>"
            ok = rules.enable(rest)
            return f"Rule enabled: {rest}" if ok else f"Rule not found: {rest}"
        if sub == "disable":
            if not rest:
                return "Usage: /notify-rules disable <name>"
            ok = rules.disable(rest)
            return f"Rule disabled: {rest}" if ok else f"Rule not found: {rest}"
        if sub == "list":
            all_rules = rules.rules()
            if not all_rules:
                return "No notification rules."
            lines = [f"  {r.name}: {r.event} ({r.level}) enabled={r.enabled}" for r in all_rules]
            return "Notification rules:\n" + "\n".join(lines)
        return "Usage: /notify-rules [add <name> <event> | remove <name> | enable <name> | disable <name> | list]"

    # ------------------------------------------------------------------
    # /notify-history
    # ------------------------------------------------------------------

    async def notify_history_handler(args: str) -> str:
        from lidco.notify.history import NotificationHistory

        history = NotificationHistory()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            entries = history.all_entries()
            if not entries:
                return "No notification history entries."
            lines = [f"  {e.id}: [{e.level}] {e.title} - {e.message}" for e in entries]
            return "History entries:\n" + "\n".join(lines)
        if sub == "search":
            if not rest:
                return "Usage: /notify-history search <query>"
            results = history.search(rest)
            if not results:
                return f"No entries matching '{rest}'."
            lines = [f"  {e.id}: [{e.level}] {e.title}" for e in results]
            return "Search results:\n" + "\n".join(lines)
        if sub == "dismiss":
            if not rest:
                return "Usage: /notify-history dismiss <id>"
            ok = history.dismiss(rest)
            return f"Entry dismissed: {rest}" if ok else f"Entry not found: {rest}"
        if sub == "snooze":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /notify-history snooze <id> <seconds>"
            ok = history.snooze(tokens[0], float(tokens[1]))
            return f"Entry snoozed: {tokens[0]}" if ok else f"Entry not found: {tokens[0]}"
        if sub == "clear":
            count = history.clear()
            return f"Cleared {count} entries."
        if sub == "export":
            fmt = rest if rest else "json"
            data = history.export(fmt)
            return data
        return "Usage: /notify-history [list | search <query> | dismiss <id> | snooze <id> <seconds> | clear | export]"

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------

    registry.register(SlashCommand("notify", "Desktop notifications: send/enable/disable/history", notify_handler))
    registry.register(SlashCommand("sound", "Sound events: play/mute/unmute/register/list", sound_handler))
    registry.register(SlashCommand("notify-rules", "Notification rules: add/remove/enable/disable/list", notify_rules_handler))
    registry.register(SlashCommand("notify-history", "Notification history: list/search/dismiss/snooze/clear/export", notify_history_handler))
