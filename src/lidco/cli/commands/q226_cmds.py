"""Q226 CLI commands: /gateway, /api-keys, /api-usage, /api-queue."""
from __future__ import annotations

import json


def register(registry) -> None:
    """Register Q226 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /gateway
    # ------------------------------------------------------------------

    async def gateway_handler(args: str) -> str:
        """
        Usage: /gateway endpoints
               /gateway add <name> <url>
               /gateway remove <name>
               /gateway health
        """
        from lidco.gateway.api_gateway import ApiGateway

        parts = args.strip().split() if args.strip() else []
        if not parts:
            return (
                "Usage: /gateway <subcommand>\n"
                "  endpoints         list all endpoints\n"
                "  add <name> <url>  add an endpoint\n"
                "  remove <name>     remove an endpoint\n"
                "  health            show health summary"
            )

        gw = ApiGateway()
        subcmd = parts[0].lower()

        if subcmd == "endpoints":
            summary = gw.summary()
            return json.dumps(summary, indent=2)
        elif subcmd == "add":
            if len(parts) < 3:
                return "Error: Usage: /gateway add <name> <url>"
            ep = gw.add_endpoint(parts[1], parts[2])
            return f"Added endpoint '{ep.name}' -> {ep.url}"
        elif subcmd == "remove":
            if len(parts) < 2:
                return "Error: Usage: /gateway remove <name>"
            removed = gw.remove_endpoint(parts[1])
            return f"Removed '{parts[1]}'" if removed else f"Endpoint '{parts[1]}' not found"
        elif subcmd == "health":
            summary = gw.summary()
            return f"{summary['healthy']}/{summary['total']} endpoints healthy"
        else:
            return f"Unknown subcommand: {subcmd}"

    # ------------------------------------------------------------------
    # /api-keys
    # ------------------------------------------------------------------

    async def api_keys_handler(args: str) -> str:
        """
        Usage: /api-keys add <provider> <key>
               /api-keys rotate <provider>
               /api-keys list
        """
        from lidco.gateway.key_rotator import KeyRotator

        parts = args.strip().split() if args.strip() else []
        if not parts:
            return (
                "Usage: /api-keys <subcommand>\n"
                "  add <provider> <key>  add an API key\n"
                "  rotate <provider>     get next key for provider\n"
                "  list                  show summary"
            )

        kr = KeyRotator()
        subcmd = parts[0].lower()

        if subcmd == "add":
            if len(parts) < 3:
                return "Error: Usage: /api-keys add <provider> <key>"
            ak = kr.add_key(parts[1], parts[2])
            return f"Added key for provider '{ak.provider}'"
        elif subcmd == "rotate":
            if len(parts) < 2:
                return "Error: Usage: /api-keys rotate <provider>"
            nk = kr.next_key(parts[1])
            if nk is None:
                return f"No available keys for '{parts[1]}'"
            return f"Next key for '{parts[1]}': {nk.key[:8]}..."
        elif subcmd == "list":
            return json.dumps(kr.summary(), indent=2)
        else:
            return f"Unknown subcommand: {subcmd}"

    # ------------------------------------------------------------------
    # /api-usage
    # ------------------------------------------------------------------

    async def api_usage_handler(args: str) -> str:
        """
        Usage: /api-usage daily
               /api-usage monthly
               /api-usage quota
               /api-usage export
        """
        from lidco.gateway.usage_tracker import UsageTracker

        parts = args.strip().split() if args.strip() else []
        if not parts:
            return (
                "Usage: /api-usage <subcommand>\n"
                "  daily    daily aggregation\n"
                "  monthly  monthly aggregation\n"
                "  quota    check quota usage\n"
                "  export   export CSV"
            )

        tracker = UsageTracker()
        subcmd = parts[0].lower()

        if subcmd == "daily":
            return json.dumps(tracker.daily(), indent=2)
        elif subcmd == "monthly":
            return json.dumps(tracker.monthly(), indent=2)
        elif subcmd == "quota":
            provider = parts[1] if len(parts) > 1 else "default"
            return json.dumps(tracker.quota_check(provider), indent=2)
        elif subcmd == "export":
            return tracker.export_csv() or "No records to export."
        else:
            return f"Unknown subcommand: {subcmd}"

    # ------------------------------------------------------------------
    # /api-queue
    # ------------------------------------------------------------------

    async def api_queue_handler(args: str) -> str:
        """
        Usage: /api-queue status
               /api-queue enqueue <provider> <payload>
               /api-queue expire
        """
        from lidco.gateway.request_queue import RequestQueue

        parts = args.strip().split(maxsplit=2) if args.strip() else []
        if not parts:
            return (
                "Usage: /api-queue <subcommand>\n"
                "  status                    show queue status\n"
                "  enqueue <provider> <payload>  add request\n"
                "  expire                    remove timed-out requests"
            )

        queue = RequestQueue()
        subcmd = parts[0].lower()

        if subcmd == "status":
            return json.dumps(queue.summary(), indent=2)
        elif subcmd == "enqueue":
            if len(parts) < 3:
                return "Error: Usage: /api-queue enqueue <provider> <payload>"
            req = queue.enqueue(parts[1], parts[2])
            return f"Enqueued request {req.id} for '{req.provider}'"
        elif subcmd == "expire":
            count = queue.expire_timeouts()
            return f"Expired {count} timed-out requests"
        else:
            return f"Unknown subcommand: {subcmd}"

    registry.register(
        SlashCommand("gateway", "API gateway endpoint management", gateway_handler)
    )
    registry.register(
        SlashCommand("api-keys", "API key rotation management", api_keys_handler)
    )
    registry.register(
        SlashCommand("api-usage", "API usage tracking and quotas", api_usage_handler)
    )
    registry.register(
        SlashCommand("api-queue", "API request queue management", api_queue_handler)
    )
