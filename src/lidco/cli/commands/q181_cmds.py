"""Q181 CLI commands: /template, /recipe, /team-templates, /approve."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q181 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /template
    # ------------------------------------------------------------------

    async def template_handler(args: str) -> str:
        from lidco.templates.conversation import (
            ConversationRenderer,
            ConversationTemplate,
            ConversationTurn,
            TemplateVariable,
            template_to_yaml,
        )

        if "renderer" not in _state:
            _state["renderer"] = ConversationRenderer()
        renderer: ConversationRenderer = _state["renderer"]  # type: ignore[assignment]

        if "templates" not in _state:
            _state["templates"] = {}
        templates: dict[str, ConversationTemplate] = _state["templates"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            if not templates:
                return "No conversation templates loaded."
            lines = [f"{len(templates)} template(s):"]
            for name, tmpl in templates.items():
                lines.append(f"  {name} v{tmpl.version} — {tmpl.description}")
            return "\n".join(lines)

        if sub == "show":
            if not rest:
                return "Usage: /template show <name>"
            tmpl = templates.get(rest)
            if tmpl is None:
                return f"Template '{rest}' not found."
            return template_to_yaml(tmpl)

        if sub == "render":
            if not rest:
                return "Usage: /template render <name>"
            tmpl = templates.get(rest)
            if tmpl is None:
                return f"Template '{rest}' not found."
            text = renderer.render_text(tmpl)
            return text or "(empty render)"

        return (
            "Usage: /template <subcommand>\n"
            "  list             — list all templates\n"
            "  show <name>      — show template YAML\n"
            "  render <name>    — render template"
        )

    # ------------------------------------------------------------------
    # /recipe
    # ------------------------------------------------------------------

    async def recipe_handler(args: str) -> str:
        from lidco.templates.recipe_engine import RecipeEngine

        if "engine" not in _state:
            _state["engine"] = RecipeEngine()
        engine: RecipeEngine = _state["engine"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            recipes = engine.list_recipes()
            if not recipes:
                return "No recipes registered."
            lines = [f"{len(recipes)} recipe(s):"]
            for r in recipes:
                lines.append(f"  {r.name} v{r.version} — {r.description}")
            return "\n".join(lines)

        if sub == "run":
            if not rest:
                return "Usage: /recipe run <name>"
            try:
                results = engine.execute(rest)
                lines = [f"Recipe '{rest}' finished with {len(results)} step(s):"]
                for sr in results:
                    lines.append(f"  {sr.step_name}: {sr.status.value}")
                return "\n".join(lines)
            except Exception as exc:
                return f"Recipe execution failed: {exc}"

        if sub == "status":
            if not rest:
                return "Usage: /recipe status <name>"
            status = engine.get_status(rest)
            return f"Recipe '{rest}' status: {status.value}"

        return (
            "Usage: /recipe <subcommand>\n"
            "  list             — list all recipes\n"
            "  run <name>       — execute a recipe\n"
            "  status <name>    — check recipe status"
        )

    # ------------------------------------------------------------------
    # /team-templates
    # ------------------------------------------------------------------

    async def team_templates_handler(args: str) -> str:
        from lidco.templates.team_registry import TeamTemplateRegistry

        if "team_registry" not in _state:
            _state["team_registry"] = TeamTemplateRegistry()
        reg: TeamTemplateRegistry = _state["team_registry"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            entries = reg.list_entries()
            if not entries:
                return "No team templates registered."
            lines = [f"{len(entries)} team template(s):"]
            for e in entries:
                lines.append(f"  {e.name} v{e.version} by {e.author or 'unknown'}")
            return "\n".join(lines)

        if sub == "search":
            if not rest:
                return "Usage: /team-templates search <query>"
            results = reg.search(rest)
            if not results:
                return f"No templates found for '{rest}'."
            lines = [f"Found {len(results)} template(s):"]
            for e in results:
                lines.append(f"  {e.name} v{e.version}")
            return "\n".join(lines)

        if sub == "info":
            if not rest:
                return "Usage: /team-templates info <name>"
            entry = reg.get(rest)
            if entry is None:
                return f"Template '{rest}' not found."
            return (
                f"Name: {entry.name}\n"
                f"Version: {entry.version}\n"
                f"Author: {entry.author}\n"
                f"Checksum: {entry.checksum}"
            )

        return (
            "Usage: /team-templates <subcommand>\n"
            "  list             — list all team templates\n"
            "  search <query>   — search templates\n"
            "  info <name>      — show template details"
        )

    # ------------------------------------------------------------------
    # /approve
    # ------------------------------------------------------------------

    async def approve_handler(args: str) -> str:
        from lidco.templates.approval_gate import ApprovalManager

        if "approval" not in _state:
            _state["approval"] = ApprovalManager()
        mgr: ApprovalManager = _state["approval"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            requests = mgr.list_requests(status="pending")
            if not requests:
                return "No pending approval requests."
            lines = [f"{len(requests)} pending request(s):"]
            for req in requests:
                lines.append(f"  {req.gate_name} by {req.requester} — {req.status}")
            return "\n".join(lines)

        if sub == "approve":
            if not rest:
                return "Usage: /approve approve <request-id> [reason]"
            id_parts = rest.split(maxsplit=1)
            req_id = id_parts[0]
            reason = id_parts[1] if len(id_parts) > 1 else ""
            try:
                req = mgr.approve(req_id, reason)
                return f"Approved request for gate '{req.gate_name}'."
            except Exception as exc:
                return f"Approve failed: {exc}"

        if sub == "reject":
            if not rest:
                return "Usage: /approve reject <request-id> [reason]"
            id_parts = rest.split(maxsplit=1)
            req_id = id_parts[0]
            reason = id_parts[1] if len(id_parts) > 1 else ""
            try:
                req = mgr.reject(req_id, reason)
                return f"Rejected request for gate '{req.gate_name}'."
            except Exception as exc:
                return f"Reject failed: {exc}"

        if sub == "audit":
            log = mgr.audit_log()
            if not log:
                return "No audit entries."
            lines = [f"{len(log)} audit entries:"]
            for entry in log:
                lines.append(
                    f"  [{entry['id']}] {entry['gate_name']}: "
                    f"{entry['status']} by {entry['requester']}"
                )
            return "\n".join(lines)

        return (
            "Usage: /approve <subcommand>\n"
            "  list             — list pending requests\n"
            "  approve <id>     — approve a request\n"
            "  reject <id>      — reject a request\n"
            "  audit            — show audit log"
        )

    registry.register(SlashCommand("template", "Conversation templates", template_handler))
    registry.register(SlashCommand("recipe", "Workflow recipes", recipe_handler))
    registry.register(SlashCommand("team-templates", "Team template registry", team_templates_handler))
    registry.register(SlashCommand("approve", "Approval gate management", approve_handler))
