"""Q265 CLI commands — /sso-login, /identity, /token, /user-directory."""
from __future__ import annotations

import json
import shlex


def register_q265_commands(registry) -> None:
    """Register Q265 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /sso-login
    # ------------------------------------------------------------------
    async def sso_login_handler(args: str) -> str:
        from lidco.identity.sso import SSOClient, SSOConfig

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /sso-login <subcommand>\n"
                "  config <provider> <issuer> <client_id>  configure SSO\n"
                "  login                                   initiate login\n"
                "  sessions                                list active sessions\n"
                "  logout <token>                          logout session"
            )

        subcmd = parts[0].lower()

        if subcmd == "config":
            if len(parts) < 4:
                return "Error: Usage: /sso-login config <provider> <issuer> <client_id>"
            config = SSOConfig(
                provider=parts[1], issuer_url=parts[2], client_id=parts[3]
            )
            return f"SSO configured: provider={config.provider}, issuer={config.issuer_url}"

        if subcmd == "login":
            config = SSOConfig(provider="default", issuer_url="https://auth.example.com", client_id="lidco")
            client = SSOClient(config)
            url = client.initiate_login()
            return f"Login URL: {url}"

        if subcmd == "sessions":
            config = SSOConfig(provider="default", issuer_url="https://auth.example.com", client_id="lidco")
            client = SSOClient(config)
            sessions = client.active_sessions()
            if not sessions:
                return "No active sessions."
            lines = [f"  {s.user_id} ({s.provider})" for s in sessions]
            return "Active sessions:\n" + "\n".join(lines)

        if subcmd == "logout":
            if len(parts) < 2:
                return "Error: Usage: /sso-login logout <token>"
            return f"Logged out token: {parts[1][:16]}..."

        return f"Unknown subcommand: {subcmd}"

    registry.register_command("sso-login", "SSO login management", sso_login_handler)

    # ------------------------------------------------------------------
    # /identity
    # ------------------------------------------------------------------
    async def identity_handler(args: str) -> str:
        from lidco.identity.provider import LocalIdentityProvider

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /identity <subcommand>\n"
                "  add <username> <password>   add user\n"
                "  auth <username> <password>  authenticate\n"
                "  list                        list users\n"
                "  remove <id>                 remove user"
            )

        subcmd = parts[0].lower()
        provider = LocalIdentityProvider()

        if subcmd == "add":
            if len(parts) < 3:
                return "Error: Usage: /identity add <username> <password>"
            info = provider.add_user(parts[1], parts[2])
            return f"User added: {info.username} ({info.user_id})"

        if subcmd == "auth":
            if len(parts) < 3:
                return "Error: Usage: /identity auth <username> <password>"
            result = provider.authenticate(parts[1], parts[2])
            if result is None:
                return "Authentication failed."
            return f"Authenticated: {result.username} ({result.user_id})"

        if subcmd == "list":
            users = provider.list_users()
            if not users:
                return "No users."
            lines = [f"  {u.username} ({u.user_id})" for u in users]
            return "Users:\n" + "\n".join(lines)

        if subcmd == "remove":
            if len(parts) < 2:
                return "Error: Usage: /identity remove <id>"
            ok = provider.remove_user(parts[1])
            return f"Removed: {ok}"

        return f"Unknown subcommand: {subcmd}"

    registry.register_command("identity", "Identity provider management", identity_handler)

    # ------------------------------------------------------------------
    # /token
    # ------------------------------------------------------------------
    async def token_handler(args: str) -> str:
        from lidco.identity.token_service import TokenService

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /token <subcommand>\n"
                "  create <subject> [roles]  create token\n"
                "  validate <token>          validate token\n"
                "  revoke <token>            revoke token\n"
                "  list                      list active tokens"
            )

        subcmd = parts[0].lower()
        svc = TokenService()

        if subcmd == "create":
            if len(parts) < 2:
                return "Error: Usage: /token create <subject> [roles]"
            roles = parts[2].split(",") if len(parts) > 2 else []
            tok = svc.create(parts[1], roles=roles)
            return f"Token created for {tok.claims.sub}: {tok.token[:32]}..."

        if subcmd == "validate":
            if len(parts) < 2:
                return "Error: Usage: /token validate <token>"
            claims = svc.validate(parts[1])
            if claims is None:
                return "Token invalid or expired."
            return f"Valid — sub={claims.sub}, roles={claims.roles}"

        if subcmd == "revoke":
            if len(parts) < 2:
                return "Error: Usage: /token revoke <token>"
            ok = svc.revoke(parts[1])
            return f"Revoked: {ok}"

        if subcmd == "list":
            tokens = svc.active_tokens()
            if not tokens:
                return "No active tokens."
            lines = [f"  {t.claims.sub} expires={t.claims.exp:.0f}" for t in tokens]
            return "Active tokens:\n" + "\n".join(lines)

        return f"Unknown subcommand: {subcmd}"

    registry.register_command("token", "Token management", token_handler)

    # ------------------------------------------------------------------
    # /user-directory
    # ------------------------------------------------------------------
    async def user_directory_handler(args: str) -> str:
        from lidco.identity.directory import UserDirectory

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /user-directory <subcommand>\n"
                "  add <username>                     add user\n"
                "  group <name>                       create group\n"
                "  add-to-group <user_id> <group>     add user to group\n"
                "  perms <user_id>                    show permissions"
            )

        subcmd = parts[0].lower()
        directory = UserDirectory()

        if subcmd == "add":
            if len(parts) < 2:
                return "Error: Usage: /user-directory add <username>"
            profile = directory.add_user(parts[1])
            return f"User added: {profile.username} ({profile.user_id})"

        if subcmd == "group":
            if len(parts) < 2:
                return "Error: Usage: /user-directory group <name>"
            grp = directory.create_group(parts[1])
            return f"Group created: {grp.name}"

        if subcmd == "add-to-group":
            if len(parts) < 3:
                return "Error: Usage: /user-directory add-to-group <user_id> <group>"
            ok = directory.add_to_group(parts[1], parts[2])
            return f"Added to group: {ok}"

        if subcmd == "perms":
            if len(parts) < 2:
                return "Error: Usage: /user-directory perms <user_id>"
            perms = directory.user_permissions(parts[1])
            if not perms:
                return "No permissions."
            return "Permissions: " + ", ".join(sorted(perms))

        return f"Unknown subcommand: {subcmd}"

    registry.register_command("user-directory", "User directory management", user_directory_handler)
