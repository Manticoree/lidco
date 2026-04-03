"""Q259 CLI commands: /roles, /permissions, /policy, /auth."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q259 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /roles
    # ------------------------------------------------------------------

    async def roles_handler(args: str) -> str:
        from lidco.rbac.roles import RoleRegistry, Role

        if "role_registry" not in _state:
            _state["role_registry"] = RoleRegistry()

        reg: RoleRegistry = _state["role_registry"]  # type: ignore[assignment]
        parts = args.strip().split(None, 2)
        sub = parts[0] if parts else "list"

        if sub == "list":
            roles = reg.all_roles()
            if not roles:
                return "No roles registered."
            lines = [f"  {r.name}: {r.description}" for r in roles]
            return "Roles:\n" + "\n".join(lines)

        if sub == "create":
            if len(parts) < 2:
                return "Usage: /roles create <name> [description]"
            name = parts[1]
            desc = parts[2] if len(parts) > 2 else ""
            role = reg.register(Role(name=name, description=desc))
            return f"Created role: {role.name}"

        if sub == "info":
            if len(parts) < 2:
                return "Usage: /roles info <name>"
            role = reg.get(parts[1])
            if role is None:
                return f"Role not found: {parts[1]}"
            perms = reg.resolve_permissions(role.name)
            return f"Role: {role.name}\nDescription: {role.description}\nPermissions: {', '.join(sorted(perms))}"

        if sub == "delete":
            if len(parts) < 2:
                return "Usage: /roles delete <name>"
            if reg.remove(parts[1]):
                return f"Deleted role: {parts[1]}"
            return f"Cannot delete role: {parts[1]}"

        return "Usage: /roles [list | create <name> | info <name> | delete <name>]"

    # ------------------------------------------------------------------
    # /permissions
    # ------------------------------------------------------------------

    async def permissions_handler(args: str) -> str:
        from lidco.rbac.roles import RoleRegistry
        from lidco.rbac.checker import PermissionChecker

        if "role_registry" not in _state:
            _state["role_registry"] = RoleRegistry()
        if "checker" not in _state:
            _state["checker"] = PermissionChecker(_state["role_registry"])  # type: ignore[arg-type]

        checker: PermissionChecker = _state["checker"]  # type: ignore[assignment]
        parts = args.strip().split()
        sub = parts[0] if parts else "help"

        if sub == "check":
            if len(parts) < 3:
                return "Usage: /permissions check <user> <permission>"
            result = checker.check(parts[1], parts[2])
            status = "ALLOWED" if result.allowed else "DENIED"
            return f"{status}: {result.reason} (role={result.role})"

        if sub == "assign":
            if len(parts) < 3:
                return "Usage: /permissions assign <user> <role>"
            if checker.assign_role(parts[1], parts[2]):
                return f"Assigned {parts[2]} to {parts[1]}"
            return f"Failed to assign role: {parts[2]}"

        if sub == "history":
            items = checker.history(limit=20)
            if not items:
                return "No permission checks recorded."
            lines = [f"  {r.permission} -> {'ALLOWED' if r.allowed else 'DENIED'} ({r.role})" for r in items[-10:]]
            return "Recent checks:\n" + "\n".join(lines)

        return "Usage: /permissions [check <user> <perm> | assign <user> <role> | history]"

    # ------------------------------------------------------------------
    # /policy
    # ------------------------------------------------------------------

    async def policy_handler(args: str) -> str:
        from lidco.rbac.policy import PolicyEngine, Policy, PolicyCondition
        import json as _json

        if "policy_engine" not in _state:
            _state["policy_engine"] = PolicyEngine()

        engine: PolicyEngine = _state["policy_engine"]  # type: ignore[assignment]
        parts = args.strip().split(None, 3)
        sub = parts[0] if parts else "list"

        if sub == "list":
            policies = engine.policies()
            if not policies:
                return "No policies defined."
            lines = [f"  {p.name}: {p.effect} (priority={p.priority})" for p in policies]
            return "Policies:\n" + "\n".join(lines)

        if sub == "add":
            if len(parts) < 3:
                return "Usage: /policy add <name> <allow|deny>"
            engine.add_policy(Policy(name=parts[1], effect=parts[2]))
            return f"Added policy: {parts[1]} ({parts[2]})"

        if sub == "eval":
            if len(parts) < 2:
                return "Usage: /policy eval <json_context>"
            raw = args.strip()[len("eval"):].strip()
            try:
                ctx = _json.loads(raw)
            except _json.JSONDecodeError as exc:
                return f"Invalid JSON: {exc}"
            result = engine.evaluate(ctx)
            return f"Evaluation result: {result}"

        if sub == "remove":
            if len(parts) < 2:
                return "Usage: /policy remove <name>"
            if engine.remove_policy(parts[1]):
                return f"Removed policy: {parts[1]}"
            return f"Policy not found: {parts[1]}"

        return "Usage: /policy [list | add <name> <effect> | eval <json_context> | remove <name>]"

    # ------------------------------------------------------------------
    # /auth
    # ------------------------------------------------------------------

    async def auth_handler(args: str) -> str:
        from lidco.rbac.session_auth import SessionAuth

        if "session_auth" not in _state:
            _state["session_auth"] = SessionAuth()

        auth: SessionAuth = _state["session_auth"]  # type: ignore[assignment]
        parts = args.strip().split()
        sub = parts[0] if parts else "help"

        if sub == "login":
            if len(parts) < 2:
                return "Usage: /auth login <user> [role]"
            user = parts[1]
            role = parts[2] if len(parts) > 2 else "viewer"
            token = auth.create_token(user, role)
            return f"Token: {token.token}\nUser: {token.user}\nRole: {token.role}"

        if sub == "validate":
            if len(parts) < 2:
                return "Usage: /auth validate <token>"
            result = auth.validate(parts[1])
            if result is None:
                return "Token is invalid or expired."
            return f"Valid token for {result.user} (role={result.role})"

        if sub == "logout":
            if len(parts) < 2:
                return "Usage: /auth logout <token>"
            if auth.revoke(parts[1]):
                return "Token revoked."
            return "Token not found."

        if sub == "sessions":
            active = auth.active_sessions()
            if not active:
                return "No active sessions."
            lines = [f"  {t.user} ({t.role}): {t.token[:12]}..." for t in active]
            return "Active sessions:\n" + "\n".join(lines)

        return "Usage: /auth [login <user> [role] | validate <token> | logout <token> | sessions]"

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------
    registry.register(SlashCommand("roles", "Manage RBAC roles", roles_handler))
    registry.register(SlashCommand("permissions", "Check and assign permissions", permissions_handler))
    registry.register(SlashCommand("policy", "Manage ABAC policies", policy_handler))
    registry.register(SlashCommand("auth", "Session authentication", auth_handler))
