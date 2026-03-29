"""Q116 CLI commands: /team."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q116 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def team_handler(args: str) -> str:
        from lidco.agents.team_registry import AgentTeamRegistry, AgentTeam, TeamNotFoundError
        from lidco.agents.shared_task_list import SharedTaskList
        from lidco.agents.team_coordinator import TeamCoordinator
        from lidco.agents.teammate_challenge import ChallengeProtocol

        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "create":
            if len(parts) < 3:
                return "Usage: /team create <name> <roles_json>"
            name = parts[1]
            try:
                roles = json.loads(parts[2])
            except json.JSONDecodeError as exc:
                return f"Invalid JSON: {exc}"
            if not isinstance(roles, dict):
                return "Roles must be a JSON object."

            if "registry" not in _state:
                _state["registry"] = AgentTeamRegistry()
            reg: AgentTeamRegistry = _state["registry"]  # type: ignore[assignment]
            team = AgentTeam(name=name, roles=roles)
            reg.register(team)
            _state["current_team"] = name
            _state["task_list"] = SharedTaskList()
            _state["challenge"] = ChallengeProtocol()
            return f"Team '{name}' created with {len(roles)} role(s)."

        if sub == "assign":
            if len(parts) < 2:
                return "Usage: /team assign <task>"
            task_title = parts[1]
            if len(parts) > 2:
                task_title = parts[1] + " " + parts[2]
            if "task_list" not in _state:
                return "No team created. Use /team create first."
            tl: SharedTaskList = _state["task_list"]  # type: ignore[assignment]
            task = tl.add(task_title)
            return f"Task '{task.id}' added: {task.title}"

        if sub == "status":
            if "current_team" not in _state:
                return "No team created. Use /team create first."
            reg = _state.get("registry")
            if reg is None:
                return "No team created. Use /team create first."
            try:
                team = reg.get(_state["current_team"])  # type: ignore[union-attr]
            except TeamNotFoundError:
                return "Team not found."
            tl = _state.get("task_list")
            pending = tl.pending_count() if tl else 0  # type: ignore[union-attr]
            roles_str = ", ".join(team.roles.keys()) if team.roles else "(none)"
            return (
                f"Team: {team.name}\n"
                f"Roles: {roles_str}\n"
                f"Pending tasks: {pending}"
            )

        if sub == "challenge":
            if len(parts) < 2:
                return "Usage: /team challenge <finding>"
            finding = parts[1]
            if len(parts) > 2:
                finding = parts[1] + " " + parts[2]
            if "challenge" not in _state:
                return "No team created. Use /team create first."
            cp: ChallengeProtocol = _state["challenge"]  # type: ignore[assignment]
            req = cp.issue(challenger="user", target="team", finding=finding)
            return f"Challenge issued: {req.id}"

        if sub == "run":
            if len(parts) < 2:
                return "Usage: /team run <prompt>"
            prompt = parts[1]
            if len(parts) > 2:
                prompt = parts[1] + " " + parts[2]
            team_obj = None
            if "registry" in _state and "current_team" in _state:
                try:
                    team_obj = _state["registry"].get(_state["current_team"])  # type: ignore[union-attr]
                except Exception:
                    pass
            coord = TeamCoordinator(team=team_obj)
            # Stub teammate fns: each just returns a string
            fns: dict[str, object] = {}
            if team_obj and team_obj.roles:  # type: ignore[union-attr]
                for role in team_obj.roles:  # type: ignore[union-attr]
                    fns[role] = lambda t, r=role: f"[{r}] done: {t}"
            cr = coord.run(prompt, fns, timeout_s=5.0)  # type: ignore[arg-type]
            lines = [f"Prompt: {cr.prompt}", f"Tasks: {cr.tasks_created}"]
            for tid, out in cr.outputs.items():
                lines.append(f"  {tid}: {out}")
            if cr.errors:
                lines.append(f"Errors: {', '.join(cr.errors)}")
            return "\n".join(lines)

        return (
            "Usage: /team <sub>\n"
            "  create <name> <roles_json>  -- create a team\n"
            "  assign <task>               -- add task to list\n"
            "  status                      -- show team info\n"
            "  challenge <finding>         -- issue challenge\n"
            "  run <prompt>                -- run coordinator"
        )

    registry.register(SlashCommand("team", "Agent team management", team_handler))
