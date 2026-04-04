"""
Q298 CLI commands — /webhook-server, /webhook-send, /event-route, /event-schema

Registered via register_q298_commands(registry).
"""
from __future__ import annotations

import json
import shlex


def register_q298_commands(registry) -> None:
    """Register Q298 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /webhook-server
    # ------------------------------------------------------------------
    async def webhook_server_handler(args: str) -> str:
        """
        Usage: /webhook-server register <path>
               /webhook-server receive <path> <json_payload>
               /webhook-server pending
               /webhook-server dead-letter
               /webhook-server verify <payload> <signature> <secret>
        """
        from lidco.webhooks.server import WebhookServer

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /webhook-server <subcommand>\n"
                "  register <path>                          register endpoint\n"
                "  receive <path> <json_payload>            receive webhook\n"
                "  pending                                  list pending events\n"
                "  dead-letter                              list dead-letter events\n"
                "  verify <payload> <signature> <secret>    verify HMAC signature"
            )

        subcmd = parts[0].lower()
        server = WebhookServer()

        if subcmd == "register":
            if len(parts) < 2:
                return "Error: path required."
            path = parts[1]
            server.register_endpoint(path, lambda p, h: {"echo": p})
            return f"Endpoint registered: {path}"

        if subcmd == "receive":
            if len(parts) < 3:
                return "Error: path and JSON payload required."
            path = parts[1]
            try:
                payload = json.loads(parts[2])
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"
            result = server.receive(path, payload)
            return json.dumps(result, indent=2)

        if subcmd == "pending":
            events = server.pending_events()
            if not events:
                return "No pending events."
            lines = [f"  {e.id}: {e.path}" for e in events]
            return f"Pending events ({len(events)}):\n" + "\n".join(lines)

        if subcmd == "dead-letter":
            events = server.dead_letter()
            if not events:
                return "No dead-letter events."
            lines = [f"  {e.id}: {e.path} — {e.error}" for e in events]
            return f"Dead-letter events ({len(events)}):\n" + "\n".join(lines)

        if subcmd == "verify":
            if len(parts) < 4:
                return "Error: payload, signature, and secret required."
            ok = WebhookServer.verify_signature(parts[1], parts[2], parts[3])
            return f"Signature valid: {ok}"

        return f"Unknown subcommand: {subcmd}"

    # ------------------------------------------------------------------
    # /webhook-send
    # ------------------------------------------------------------------
    async def webhook_send_handler(args: str) -> str:
        """
        Usage: /webhook-send <url> <json_payload> [--secret <secret>] [--retry <n>]
               /webhook-send log
        """
        from lidco.webhooks.client import WebhookClient

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /webhook-send <url> <json_payload> [--secret <s>] [--retry <n>]\n"
                "       /webhook-send log"
            )

        if parts[0].lower() == "log":
            client = WebhookClient()
            records = client.delivery_log()
            if not records:
                return "No delivery records."
            lines = [f"  {r.url}: {r.status}" for r in records]
            return f"Delivery log ({len(records)}):\n" + "\n".join(lines)

        if len(parts) < 2:
            return "Error: URL and JSON payload required."

        url = parts[0]
        try:
            payload = json.loads(parts[1])
        except json.JSONDecodeError as exc:
            return f"Error: invalid JSON — {exc}"

        secret = ""
        max_retries = 0
        i = 2
        while i < len(parts):
            if parts[i] == "--secret" and i + 1 < len(parts):
                secret = parts[i + 1]
                i += 2
            elif parts[i] == "--retry" and i + 1 < len(parts):
                max_retries = int(parts[i + 1])
                i += 2
            else:
                i += 1

        client = WebhookClient(default_secret=secret)
        if max_retries > 0:
            result = client.with_retry(url, payload, max_retries=max_retries)
        else:
            result = client.send(url, payload)
        return json.dumps(result, indent=2)

    # ------------------------------------------------------------------
    # /event-route
    # ------------------------------------------------------------------
    async def event_route_handler(args: str) -> str:
        """
        Usage: /event-route add <pattern>
               /event-route dispatch <event_type> <json_data>
               /event-route list
        """
        from lidco.webhooks.router import EventRouter2, RoutedEvent

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /event-route <subcommand>\n"
                "  add <pattern>                    add route\n"
                "  dispatch <type> <json_data>      dispatch event\n"
                "  list                             list routes"
            )

        subcmd = parts[0].lower()
        router = EventRouter2()

        if subcmd == "add":
            if len(parts) < 2:
                return "Error: pattern required."
            rid = router.add_route(parts[1], lambda e: {"matched": e.type})
            return f"Route added: {rid}"

        if subcmd == "dispatch":
            if len(parts) < 3:
                return "Error: event_type and JSON data required."
            try:
                data = json.loads(parts[2])
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"
            event = RoutedEvent(type=parts[1], data=data)
            results = router.route(event)
            return json.dumps(results, indent=2)

        if subcmd == "list":
            if not router._routes:
                return "No routes registered."
            lines = [f"  {r.pattern} (priority={r.priority})" for r in router._routes]
            return f"Routes ({len(router._routes)}):\n" + "\n".join(lines)

        return f"Unknown subcommand: {subcmd}"

    # ------------------------------------------------------------------
    # /event-schema
    # ------------------------------------------------------------------
    async def event_schema_handler(args: str) -> str:
        """
        Usage: /event-schema register <event_type> <json_schema> [--version <v>]
               /event-schema validate <event_type> <json_payload>
               /event-schema list
               /event-schema version <event_type>
               /event-schema compatible <old_v> <new_v>
        """
        from lidco.webhooks.schemas import EventSchemaRegistry

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /event-schema <subcommand>\n"
                "  register <type> <json_schema> [--version <v>]\n"
                "  validate <type> <json_payload>\n"
                "  list\n"
                "  version <type>\n"
                "  compatible <old_v> <new_v>"
            )

        subcmd = parts[0].lower()
        reg = EventSchemaRegistry()

        if subcmd == "register":
            if len(parts) < 3:
                return "Error: event_type and JSON schema required."
            try:
                schema = json.loads(parts[2])
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"
            version = "1.0.0"
            if "--version" in parts:
                idx = parts.index("--version")
                if idx + 1 < len(parts):
                    version = parts[idx + 1]
            reg.register(parts[1], schema, version=version)
            return f"Schema registered: {parts[1]} v{version}"

        if subcmd == "validate":
            if len(parts) < 3:
                return "Error: event_type and JSON payload required."
            try:
                payload = json.loads(parts[2])
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"
            ok = reg.validate(parts[1], payload)
            return f"Valid: {ok}"

        if subcmd == "list":
            schemas = reg.list_schemas()
            if not schemas:
                return "No schemas registered."
            return "Registered schemas:\n" + "\n".join(f"  {s}" for s in schemas)

        if subcmd == "version":
            if len(parts) < 2:
                return "Error: event_type required."
            v = reg.version(parts[1])
            if not v:
                return f"No schema for: {parts[1]}"
            return f"{parts[1]}: v{v}"

        if subcmd == "compatible":
            if len(parts) < 3:
                return "Error: old_version and new_version required."
            ok = EventSchemaRegistry.is_compatible(parts[1], parts[2])
            return f"Compatible: {ok}"

        return f"Unknown subcommand: {subcmd}"

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("webhook-server", "Webhook server management", webhook_server_handler))
    registry.register(SlashCommand("webhook-send", "Send webhooks with retry/signing", webhook_send_handler))
    registry.register(SlashCommand("event-route", "Event routing with patterns", event_route_handler))
    registry.register(SlashCommand("event-schema", "Event schema registry", event_schema_handler))
