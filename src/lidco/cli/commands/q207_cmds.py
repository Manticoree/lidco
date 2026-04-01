"""Q207 CLI commands: /oauth-login, /tokens, /keychain, /mcp-auth."""

from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q207 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /oauth-login
    # ------------------------------------------------------------------

    async def oauth_login_handler(args: str) -> str:
        from lidco.auth.oauth_flow import OAuthConfig, OAuthFlow

        parts = args.strip().split()
        if len(parts) < 2:
            return "Usage: /oauth-login <client_id> <auth_url> [token_url]"
        client_id = parts[0]
        auth_url = parts[1]
        token_url = parts[2] if len(parts) > 2 else auth_url.replace("/authorize", "/token")

        config = OAuthConfig(client_id=client_id, auth_url=auth_url, token_url=token_url)
        flow = OAuthFlow(config)
        pkce = flow.generate_pkce()
        url = flow.build_auth_url(state="cli", pkce=pkce)
        return f"Visit this URL to authorize:\n{url}"

    # ------------------------------------------------------------------
    # /tokens
    # ------------------------------------------------------------------

    async def tokens_handler(args: str) -> str:
        from lidco.auth.token_manager import TokenManager

        if "token_manager" not in _state:
            _state["token_manager"] = TokenManager()
        mgr: TokenManager = _state["token_manager"]  # type: ignore[assignment]

        sub = args.strip().split(maxsplit=1)
        cmd = sub[0].lower() if sub else ""

        if cmd == "list":
            services = mgr.list_services()
            if not services:
                return "No tokens stored."
            return f"{len(services)} token(s): " + ", ".join(services)

        if cmd == "count":
            return f"Stored tokens: {mgr.token_count()}"

        if cmd == "clear":
            n = mgr.clear()
            return f"Cleared {n} token(s)."

        return "Usage: /tokens <list|count|clear>"

    # ------------------------------------------------------------------
    # /keychain
    # ------------------------------------------------------------------

    async def keychain_handler(args: str) -> str:
        from lidco.auth.keychain import KeychainStorage

        if "keychain" not in _state:
            _state["keychain"] = KeychainStorage()
        kc: KeychainStorage = _state["keychain"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=3)
        cmd = parts[0].lower() if parts else ""

        if cmd == "set" and len(parts) >= 4:
            kc.set(parts[1], parts[2], parts[3])
            return f"Stored {parts[1]}/{parts[2]}."

        if cmd == "get" and len(parts) >= 3:
            val = kc.get(parts[1], parts[2])
            if val is None:
                return f"Not found: {parts[1]}/{parts[2]}"
            return f"{parts[1]}/{parts[2]} = {val}"

        if cmd == "list":
            entries = kc.list_entries()
            if not entries:
                return "Keychain is empty."
            lines = [f"{len(entries)} entry(ies):"]
            for e in entries:
                lines.append(f"  {e.service}/{e.key}")
            return "\n".join(lines)

        if cmd == "clear":
            n = kc.clear()
            return f"Cleared {n} keychain entry(ies)."

        return "Usage: /keychain <set|get|list|clear> ..."

    # ------------------------------------------------------------------
    # /mcp-auth
    # ------------------------------------------------------------------

    async def mcp_auth_handler(args: str) -> str:
        from lidco.auth.mcp_auth import MCPAuthAdapter

        if "mcp_auth" not in _state:
            _state["mcp_auth"] = MCPAuthAdapter()
        adapter: MCPAuthAdapter = _state["mcp_auth"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=3)
        cmd = parts[0].lower() if parts else ""

        if cmd == "register" and len(parts) >= 3:
            name = parts[1]
            auth_type = parts[2]
            token = parts[3] if len(parts) > 3 else ""
            cred = adapter.register_credential(name, auth_type, token)
            return f"Registered {cred.server_name} [{cred.auth_type}]."

        if cmd == "list":
            servers = adapter.list_servers()
            if not servers:
                return "No MCP credentials registered."
            return f"{len(servers)} server(s): " + ", ".join(servers)

        if cmd == "summary":
            return adapter.summary()

        return "Usage: /mcp-auth <register|list|summary> ..."

    registry.register(SlashCommand("oauth-login", "Start OAuth login flow", oauth_login_handler))
    registry.register(SlashCommand("tokens", "Manage stored tokens", tokens_handler))
    registry.register(SlashCommand("keychain", "Manage keychain entries", keychain_handler))
    registry.register(SlashCommand("mcp-auth", "Manage MCP server credentials", mcp_auth_handler))
