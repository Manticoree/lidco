"""Q135 CLI commands: /net."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q135 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def net_handler(args: str) -> str:
        from lidco.network.url_parser import UrlParser
        from lidco.network.header_manager import HeaderManager
        from lidco.network.connection_pool import ConnectionPool

        # Lazy init
        if "parser" not in _state:
            _state["parser"] = UrlParser()
        if "headers" not in _state:
            _state["headers"] = HeaderManager()
        if "pool" not in _state:
            _state["pool"] = ConnectionPool()

        parser: UrlParser = _state["parser"]  # type: ignore[assignment]
        headers: HeaderManager = _state["headers"]  # type: ignore[assignment]
        pool: ConnectionPool = _state["pool"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "parse":
            if not rest:
                return "Usage: /net parse <url>"
            parsed = parser.parse(rest)
            return json.dumps({
                "scheme": parsed.scheme,
                "host": parsed.host,
                "port": parsed.port,
                "path": parsed.path,
                "query_params": parsed.query_params,
                "fragment": parsed.fragment,
            }, indent=2)

        if sub == "build":
            if not rest:
                return "Usage: /net build <scheme> <host> [path]"
            build_parts = rest.split()
            scheme = build_parts[0] if len(build_parts) > 0 else "https"
            host = build_parts[1] if len(build_parts) > 1 else "localhost"
            path = build_parts[2] if len(build_parts) > 2 else "/"
            return parser.build(scheme, host, path)

        if sub == "valid":
            if not rest:
                return "Usage: /net valid <url>"
            return str(parser.is_valid(rest))

        if sub == "headers":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            rest2 = sub_parts[1] if len(sub_parts) > 1 else ""
            if action == "set":
                kv = rest2.split(maxsplit=1)
                if len(kv) < 2:
                    return "Usage: /net headers set <name> <value>"
                headers.set(kv[0], kv[1])
                return f"Header set: {kv[0]}"
            if action == "get":
                val = headers.get(rest2.strip())
                if val is None:
                    return f"Header not found: {rest2.strip()}"
                return val
            if action == "remove":
                removed = headers.remove(rest2.strip())
                return f"Removed: {removed}"
            if action == "list":
                return json.dumps(headers.to_dict(), indent=2)
            return "Subcommands: set, get, remove, list"

        if sub == "pool":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            rest2 = sub_parts[1] if len(sub_parts) > 1 else ""
            if action == "acquire":
                if not rest2:
                    return "Usage: /net pool acquire <host>"
                try:
                    conn = pool.acquire(rest2.strip())
                    return f"Acquired connection {conn.id} to {conn.host}"
                except RuntimeError as exc:
                    return str(exc)
            if action == "stats":
                return json.dumps(pool.stats(), indent=2)
            if action == "evict":
                count = pool.evict_idle()
                return f"Evicted {count} idle connections."
            return "Subcommands: acquire, stats, evict"

        return "Usage: /net <parse|build|valid|headers|pool> ..."

    registry.register(SlashCommand("net", "Network utilities: URL parse/build, headers, pool", net_handler))
