"""
Q292 CLI commands — /slack-notify, /slack-command, /slack-share, /slack-config

Registered via register_q292_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q292_commands(registry) -> None:
    """Register Q292 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /slack-notify — Send notifications via Slack bridge
    # ------------------------------------------------------------------
    _notify_state: dict[str, object] = {}

    async def slack_notify_handler(args: str) -> str:
        """
        Usage: /slack-notify send <event_type> <message>
               /slack-notify configure <event_type> <channel>
               /slack-notify pending
        """
        from lidco.slack.bridge import NotificationBridge
        from lidco.slack.client import SlackClient

        if "bridge" not in _notify_state:
            _notify_state["bridge"] = NotificationBridge(SlackClient())

        bridge: NotificationBridge = _notify_state["bridge"]  # type: ignore[assignment]

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /slack-notify <subcommand>\n"
                "  send <event_type> <message>       send notification\n"
                "  configure <event_type> <channel>   map event to channel\n"
                "  pending                            show failed notifications"
            )

        subcmd = parts[0].lower()

        if subcmd == "send":
            if len(parts) < 3:
                return "Error: Usage: /slack-notify send <event_type> <message>"
            event_type = parts[1]
            message = " ".join(parts[2:])
            ok = bridge.notify(event_type, message)
            if ok:
                return f"Notification sent for '{event_type}' to #{bridge.get_channel(event_type)}."
            return f"Failed to send notification for '{event_type}'. Queued as pending."

        if subcmd == "configure":
            if len(parts) < 3:
                return "Error: Usage: /slack-notify configure <event_type> <channel>"
            try:
                bridge.configure_channel(parts[1], parts[2])
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Event '{parts[1]}' mapped to #{parts[2]}."

        if subcmd == "pending":
            items = bridge.pending()
            if not items:
                return "No pending notifications."
            lines = [f"  [{p.event_type}] {p.message}" for p in items]
            return f"Pending notifications ({len(items)}):\n" + "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use send/configure/pending."

    registry.register_async("slack-notify", "Send notifications via Slack", slack_notify_handler)

    # ------------------------------------------------------------------
    # /slack-command — Execute Slack @mention commands
    # ------------------------------------------------------------------
    _cmd_state: dict[str, object] = {}

    async def slack_command_handler(args: str) -> str:
        """
        Usage: /slack-command exec <mention_text>
               /slack-command register <cmd>
               /slack-command list
        """
        from lidco.slack.commands import CommandBridge

        if "bridge" not in _cmd_state:
            bridge = CommandBridge()
            bridge.register_handler("help", lambda a: "Available: help, status, ping")
            bridge.register_handler("status", lambda a: "All systems operational.")
            bridge.register_handler("ping", lambda a: "pong")
            _cmd_state["bridge"] = bridge

        bridge: CommandBridge = _cmd_state["bridge"]  # type: ignore[assignment]

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /slack-command <subcommand>\n"
                "  exec <mention_text>   execute a mention command\n"
                "  list                  list registered commands"
            )

        subcmd = parts[0].lower()

        if subcmd == "exec":
            if len(parts) < 2:
                return "Error: Usage: /slack-command exec <mention_text>"
            mention_text = " ".join(parts[1:])
            return bridge.execute(mention_text)

        if subcmd == "list":
            cmds = bridge.list_commands()
            if not cmds:
                return "No commands registered."
            return "Registered commands:\n" + "\n".join(f"  {c}" for c in cmds)

        return f"Unknown subcommand '{subcmd}'. Use exec/list."

    registry.register_async("slack-command", "Execute Slack mention commands", slack_command_handler)

    # ------------------------------------------------------------------
    # /slack-share — Share code snippets to Slack
    # ------------------------------------------------------------------
    _share_state: dict[str, object] = {}

    async def slack_share_handler(args: str) -> str:
        """
        Usage: /slack-share send <channel> <language> <code>
               /slack-share thread <channel> <title>
               /slack-share attach <thread_id> <filename> <content>
               /slack-share list
        """
        from lidco.slack.client import SlackClient
        from lidco.slack.code_share import CodeShare

        if "share" not in _share_state:
            _share_state["share"] = CodeShare(SlackClient())

        cs: CodeShare = _share_state["share"]  # type: ignore[assignment]

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /slack-share <subcommand>\n"
                "  send <channel> <language> <code>        share a snippet\n"
                "  thread <channel> <title>                create a thread\n"
                "  attach <thread_id> <filename> <content> attach file to thread\n"
                "  list                                    list shared snippets"
            )

        subcmd = parts[0].lower()

        if subcmd == "send":
            if len(parts) < 4:
                return "Error: Usage: /slack-share send <channel> <language> <code>"
            channel = parts[1]
            language = parts[2]
            code = " ".join(parts[3:])
            try:
                result = cs.share(code, language, channel)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Snippet shared to #{channel} (id: {result['snippet_id']}, lang: {language})."

        if subcmd == "thread":
            if len(parts) < 3:
                return "Error: Usage: /slack-share thread <channel> <title>"
            channel = parts[1]
            title = " ".join(parts[2:])
            try:
                thread_id = cs.create_thread(channel, title)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Thread created in #{channel}: {thread_id}"

        if subcmd == "attach":
            if len(parts) < 4:
                return "Error: Usage: /slack-share attach <thread_id> <filename> <content>"
            thread_id = parts[1]
            filename = parts[2]
            content = " ".join(parts[3:])
            try:
                result = cs.attach_file(thread_id, content, filename)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"File '{filename}' attached to thread {thread_id}."

        if subcmd == "list":
            snippets = cs.list_snippets()
            if not snippets:
                return "No snippets shared yet."
            lines = [
                f"  {s.snippet_id[:8]}  #{s.channel}  {s.language}  {s.length} chars"
                for s in snippets
            ]
            return f"Shared snippets ({len(snippets)}):\n" + "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use send/thread/attach/list."

    registry.register_async("slack-share", "Share code snippets to Slack", slack_share_handler)

    # ------------------------------------------------------------------
    # /slack-config — Configure Slack integration
    # ------------------------------------------------------------------
    _config_state: dict[str, str] = {}

    async def slack_config_handler(args: str) -> str:
        """
        Usage: /slack-config set <key> <value>
               /slack-config get <key>
               /slack-config list
        """
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /slack-config <subcommand>\n"
                "  set <key> <value>   set a config value\n"
                "  get <key>           get a config value\n"
                "  list                list all config values"
            )

        subcmd = parts[0].lower()

        if subcmd == "set":
            if len(parts) < 3:
                return "Error: Usage: /slack-config set <key> <value>"
            _config_state[parts[1]] = parts[2]
            return f"Config '{parts[1]}' set to '{parts[2]}'."

        if subcmd == "get":
            if len(parts) < 2:
                return "Error: Usage: /slack-config get <key>"
            val = _config_state.get(parts[1])
            if val is None:
                return f"Config '{parts[1]}' not set."
            return f"{parts[1]} = {val}"

        if subcmd == "list":
            if not _config_state:
                return "No config values set."
            lines = [f"  {k} = {v}" for k, v in sorted(_config_state.items())]
            return "Slack config:\n" + "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use set/get/list."

    registry.register_async("slack-config", "Configure Slack integration settings", slack_config_handler)
