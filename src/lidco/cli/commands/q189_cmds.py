"""Q189 CLI commands: /remote-control, /mobile, /deep-link, /session-server."""
from __future__ import annotations

from lidco.cli.commands.registry import SlashCommand

_state: dict[str, object] = {}


def register(registry) -> None:  # noqa: C901
    """Register Q189 commands with *registry*."""

    # ------------------------------------------------------------------
    # /session-server — start / stop / status of the remote session server
    # ------------------------------------------------------------------
    async def session_server_handler(args: str) -> str:
        from lidco.remote.session_server import RemoteSessionServer

        parts = args.strip().split() if args.strip() else []
        if not parts:
            return (
                "Usage: /session-server <subcommand>\n"
                "  start [--host H] [--port P]  start the server\n"
                "  stop                          stop the server\n"
                "  status                        show server info"
            )

        subcmd = parts[0].lower()

        if subcmd == "stop":
            server = _state.get("server")
            if server is None:
                return "No session server is running."
            server.stop()  # type: ignore[union-attr]
            _state.pop("server", None)
            _state.pop("info", None)
            return "Session server stopped."

        if subcmd == "status":
            server = _state.get("server")
            if server is None or not server.is_running:  # type: ignore[union-attr]
                return "Session server is not running."
            info = _state.get("info")
            if info is None:
                return "Session server is running (no info available)."
            return (
                f"Session server running at {info.url}\n"  # type: ignore[union-attr]
                f"  Clients: {server.connected_clients}"  # type: ignore[union-attr]
            )

        if subcmd == "start":
            existing = _state.get("server")
            if existing is not None and existing.is_running:  # type: ignore[union-attr]
                return "Session server is already running."
            host = "localhost"
            port = 0
            i = 1
            while i < len(parts):
                if parts[i] == "--host" and i + 1 < len(parts):
                    host = parts[i + 1]
                    i += 2
                    continue
                if parts[i] == "--port" and i + 1 < len(parts):
                    try:
                        port = int(parts[i + 1])
                    except ValueError:
                        return "Error: port must be an integer."
                    i += 2
                    continue
                i += 1
            server = RemoteSessionServer(host=host, port=port)
            info = server.start()
            _state["server"] = server
            _state["info"] = info
            return f"Session server started at {info.url} (token: {info.token[:8]}...)"

        return f"Unknown subcommand: {subcmd}"

    registry.register(SlashCommand(
        "session-server", "Start/stop/status of remote session server", session_server_handler,
    ))

    # ------------------------------------------------------------------
    # /remote-control — send a message to connected clients
    # ------------------------------------------------------------------
    async def remote_control_handler(args: str) -> str:
        server = _state.get("server")
        if server is None or not server.is_running:  # type: ignore[union-attr]
            return "Error: No session server running. Use /session-server start first."
        msg = args.strip()
        if not msg:
            return "Usage: /remote-control <message>"
        try:
            server.send_message(msg)  # type: ignore[union-attr]
        except RuntimeError as exc:
            return f"Error: {exc}"
        return f"Sent: {msg}"

    registry.register(SlashCommand(
        "remote-control", "Send a message to connected remote clients", remote_control_handler,
    ))

    # ------------------------------------------------------------------
    # /mobile — pair / notify / status
    # ------------------------------------------------------------------
    async def mobile_handler(args: str) -> str:
        from lidco.remote.mobile_bridge import MobileBridge

        parts = args.strip().split() if args.strip() else []
        if not parts:
            return (
                "Usage: /mobile <subcommand>\n"
                "  pair       generate a pairing code\n"
                "  verify <code>  verify a pairing code\n"
                "  notify <title> <body>  send notification"
            )

        subcmd = parts[0].lower()

        if subcmd == "pair":
            info = _state.get("info")
            if info is None:
                return "Error: No session server running. Use /session-server start first."
            bridge = _state.get("bridge")
            if bridge is None:
                bridge = MobileBridge(info)  # type: ignore[arg-type]
                _state["bridge"] = bridge
            pairing = bridge.generate_pairing_code()  # type: ignore[union-attr]
            return f"Pairing code: {pairing.code}\nURL: {pairing.url}\nExpires at: {pairing.expires_at:.0f}"

        if subcmd == "verify":
            bridge = _state.get("bridge")
            if bridge is None:
                return "Error: No bridge active. Use /mobile pair first."
            code = parts[1] if len(parts) > 1 else ""
            if not code:
                return "Usage: /mobile verify <code>"
            ok = bridge.verify_pairing(code)  # type: ignore[union-attr]
            return "Pairing successful." if ok else "Invalid or expired pairing code."

        if subcmd == "notify":
            bridge = _state.get("bridge")
            if bridge is None:
                return "Error: No bridge active. Use /mobile pair first."
            title = parts[1] if len(parts) > 1 else ""
            body = " ".join(parts[2:]) if len(parts) > 2 else ""
            if not title:
                return "Usage: /mobile notify <title> <body>"
            sent = bridge.send_notification(title, body)  # type: ignore[union-attr]
            return "Notification sent." if sent else "Failed: device not paired."

        return f"Unknown subcommand: {subcmd}"

    registry.register(SlashCommand(
        "mobile", "Pair mobile device, send notifications", mobile_handler,
    ))

    # ------------------------------------------------------------------
    # /deep-link — parse / generate / validate deep links
    # ------------------------------------------------------------------
    async def deep_link_handler(args: str) -> str:
        from lidco.remote.deep_links import DeepLinkHandler

        parts = args.strip().split(maxsplit=1) if args.strip() else []
        if not parts:
            return (
                "Usage: /deep-link <subcommand>\n"
                "  parse <uri>       parse a deep link\n"
                "  generate <action> [key=val ...]  generate a deep link\n"
                "  validate <uri>    check if a URI is a valid deep link"
            )

        subcmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        handler = DeepLinkHandler()

        if subcmd == "parse":
            if not rest:
                return "Usage: /deep-link parse <uri>"
            try:
                link = handler.parse(rest)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Scheme: {link.scheme}\nAction: {link.action}\nParams: {link.params}"

        if subcmd == "generate":
            tokens = rest.split()
            if not tokens:
                return "Usage: /deep-link generate <action> [key=val ...]"
            action = tokens[0]
            params: dict[str, str] = {}
            for tok in tokens[1:]:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    params[k] = v
            uri = handler.generate(action, params if params else None)
            return f"Generated: {uri}"

        if subcmd == "validate":
            if not rest:
                return "Usage: /deep-link validate <uri>"
            valid = handler.validate(rest)
            return f"Valid: {valid}"

        return f"Unknown subcommand: {subcmd}"

    registry.register(SlashCommand(
        "deep-link", "Parse, generate, or validate deep links", deep_link_handler,
    ))
