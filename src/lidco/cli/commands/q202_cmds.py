"""Q202 CLI commands: /team-create, /team-invite, /team-stats, /team-session."""

from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q202 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /team-create
    # ------------------------------------------------------------------

    async def team_create_handler(args: str) -> str:
        from lidco.teams.registry import TeamRegistry

        if "team_registry" not in _state:
            _state["team_registry"] = TeamRegistry()
        reg: TeamRegistry = _state["team_registry"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        name = parts[0] if parts else ""
        if not name:
            return "Usage: /team-create <name> [description]"
        description = parts[1] if len(parts) > 1 else ""

        team = reg.create_team(name=name, description=description, owner_id="local")
        return f"Created team '{team.name}' (id={team.id})"

    # ------------------------------------------------------------------
    # /team-invite
    # ------------------------------------------------------------------

    async def team_invite_handler(args: str) -> str:
        from lidco.teams.registry import TeamNotFoundError, TeamRegistry, TeamRole

        if "team_registry" not in _state:
            _state["team_registry"] = TeamRegistry()
        reg: TeamRegistry = _state["team_registry"]  # type: ignore[assignment]

        parts = args.strip().split()
        if len(parts) < 2:
            return "Usage: /team-invite <team_id> <user_id> [role]"
        team_id, user_id = parts[0], parts[1]
        role_str = parts[2] if len(parts) > 2 else "viewer"
        try:
            role = TeamRole(role_str.lower())
        except ValueError:
            return f"Invalid role '{role_str}'. Choose from: owner, editor, viewer."

        try:
            team = reg.add_member(team_id, user_id, role)
        except TeamNotFoundError:
            return f"Team '{team_id}' not found."
        return f"Added {user_id} as {role.value} to team '{team.name}'"

    # ------------------------------------------------------------------
    # /team-stats
    # ------------------------------------------------------------------

    async def team_stats_handler(args: str) -> str:
        from lidco.teams.analytics import TeamAnalytics

        team_id = args.strip()
        if not team_id:
            return "Usage: /team-stats <team_id>"
        analytics = TeamAnalytics(team_id)
        return analytics.summary()

    # ------------------------------------------------------------------
    # /team-session
    # ------------------------------------------------------------------

    async def team_session_handler(args: str) -> str:
        from lidco.teams.shared_session import SessionMode, SharedSession

        if "shared_session" not in _state:
            parts = args.strip().split()
            team_id = parts[0] if parts else "default"
            mode_str = parts[1] if len(parts) > 1 else "turn_based"
            try:
                mode = SessionMode(mode_str)
            except ValueError:
                mode = SessionMode.TURN_BASED
            session = SharedSession(team_id=team_id, mode=mode)
            _state["shared_session"] = session
            return f"Started shared session for team '{team_id}' in {mode.value} mode."

        session = _state["shared_session"]  # type: ignore[assignment]
        parts = args.strip().split()
        sub = parts[0].lower() if parts else "status"

        if sub == "join" and len(parts) > 1:
            session.join(parts[1])  # type: ignore[union-attr]
            return f"{parts[1]} joined the session."
        if sub == "leave" and len(parts) > 1:
            session.leave(parts[1])  # type: ignore[union-attr]
            return f"{parts[1]} left the session."
        if sub == "users":
            users = session.active_users()  # type: ignore[union-attr]
            if not users:
                return "No active users."
            return f"Active users: {', '.join(users)}"

        return (
            "Usage: /team-session <team_id> [mode]\n"
            "  join <user>  — join session\n"
            "  leave <user> — leave session\n"
            "  users        — list active users"
        )

    registry.register(SlashCommand("team-create", "Create a new team", team_create_handler))
    registry.register(SlashCommand("team-invite", "Invite member to team", team_invite_handler))
    registry.register(SlashCommand("team-stats", "Show team analytics", team_stats_handler))
    registry.register(SlashCommand("team-session", "Start/manage shared session", team_session_handler))
