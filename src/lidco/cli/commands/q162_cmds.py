"""Q162 CLI commands: /btw, /plan-mode, /workflows, /model-alias."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q162 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /btw  -- side-question fork
    # ------------------------------------------------------------------

    async def btw_handler(args: str) -> str:
        from lidco.session.side_question import SideQuestionManager

        if "sq" not in _state:
            _state["sq"] = SideQuestionManager()
        mgr: SideQuestionManager = _state["sq"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "history":
            hist = mgr.history()
            if not hist:
                return "No side-question history."
            lines = [f"  {i + 1}. Q: {r.question!r}  A: {r.answer}" for i, r in enumerate(hist)]
            return "Side-question history:\n" + "\n".join(lines)

        if sub == "clear":
            mgr.clear_history()
            return "Side-question history cleared."

        if not args.strip():
            return "Usage: /btw <question>  |  /btw history  |  /btw clear"

        result = mgr.ask(args.strip())
        return f"{result.answer}  ({result.tokens_used} tokens)"

    registry.register(SlashCommand("btw", "Ask a side question without polluting context", btw_handler))

    # ------------------------------------------------------------------
    # /plan-mode  -- read-only plan mode
    # ------------------------------------------------------------------

    async def plan_mode_handler(args: str) -> str:
        from lidco.modes.plan_mode import PlanMode

        if "pm" not in _state:
            _state["pm"] = PlanMode()
        pm: PlanMode = _state["pm"]  # type: ignore[assignment]

        sub = args.strip().lower()

        if sub == "on":
            pm.activate()
            return "Plan mode activated (read-only). Mutating operations are blocked."
        if sub == "off":
            pm.deactivate()
            return "Plan mode deactivated. All operations allowed."
        if sub == "status":
            status = "active" if pm.is_active else "inactive"
            plan = pm.get_plan()
            lines = [f"Plan mode: {status}"]
            if plan:
                lines.append(f"Plan lines: {len(pm.state().plan_output)}")
            return "\n".join(lines)
        if sub == "show":
            plan = pm.get_plan()
            return plan if plan else "No plan lines accumulated."
        if sub == "clear":
            pm.clear()
            return "Plan output cleared."

        return (
            "Usage: /plan-mode <subcommand>\n"
            "  on      -- activate read-only plan mode\n"
            "  off     -- deactivate plan mode\n"
            "  status  -- show current state\n"
            "  show    -- show accumulated plan\n"
            "  clear   -- clear plan output"
        )

    registry.register(SlashCommand("plan-mode", "Toggle read-only plan mode", plan_mode_handler))

    # ------------------------------------------------------------------
    # /workflows  -- markdown workflow loader
    # ------------------------------------------------------------------

    async def workflows_handler(args: str) -> str:
        from lidco.workflows.md_loader import WorkflowLoader

        if "wl" not in _state:
            _state["wl"] = WorkflowLoader()
        loader: WorkflowLoader = _state["wl"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list" or not sub:
            wfs = loader.load_all()
            if not wfs:
                return "No workflows found in .lidco/workflows/"
            lines = [f"  {wf.name}: {wf.title} ({len(wf.steps)} steps)" for wf in wfs]
            return "Workflows:\n" + "\n".join(lines)

        if sub == "run":
            if not rest:
                return "Usage: /workflows run <name>"
            wf = loader.load_one(rest)
            if wf is None:
                return f"Workflow '{rest}' not found."
            lines = [f"## {wf.title}", ""]
            if wf.description:
                lines.append(wf.description)
                lines.append("")
            for i, step in enumerate(wf.steps, 1):
                lines.append(f"{i}. {step}")
            return "\n".join(lines)

        if sub == "register":
            loader.register_as_commands(registry)
            wfs = loader.load_all()
            return f"Registered {len(wfs)} workflow commands."

        return (
            "Usage: /workflows <subcommand>\n"
            "  list            -- list available workflows\n"
            "  run <name>      -- run a workflow by name\n"
            "  register        -- register workflows as slash commands"
        )

    registry.register(SlashCommand("workflows", "List or run markdown workflows", workflows_handler))

    # ------------------------------------------------------------------
    # /model-alias  -- manage model aliases
    # ------------------------------------------------------------------

    async def model_alias_handler(args: str) -> str:
        from lidco.llm.model_aliases import ModelAliasRegistry

        if "ma" not in _state:
            _state["ma"] = ModelAliasRegistry()
        mar: ModelAliasRegistry = _state["ma"]  # type: ignore[assignment]

        parts = args.strip().split()
        sub = parts[0].lower() if parts else ""

        if sub == "add":
            if len(parts) < 3:
                return "Usage: /model-alias add <alias> <model>"
            alias = parts[1]
            model = parts[2]
            mar.add(alias, model)
            return f"Alias '{alias}' -> '{model}' added."

        if sub == "remove":
            if len(parts) < 2:
                return "Usage: /model-alias remove <alias>"
            alias = parts[1]
            if mar.remove(alias):
                return f"Alias '{alias}' removed."
            return f"Alias '{alias}' not found."

        if sub == "list" or not sub:
            aliases = mar.list()
            if not aliases:
                return "No model aliases configured."
            lines = [f"  {k} -> {v}" for k, v in sorted(aliases.items())]
            return "Model aliases:\n" + "\n".join(lines)

        if sub == "resolve":
            if len(parts) < 2:
                return "Usage: /model-alias resolve <name>"
            resolved = mar.resolve(parts[1])
            return f"{parts[1]} -> {resolved}"

        if sub == "save":
            path = parts[1] if len(parts) > 1 else ".lidco/model_aliases.json"
            mar.save(path)
            return f"Aliases saved to {path}"

        if sub == "load":
            path = parts[1] if len(parts) > 1 else ".lidco/model_aliases.json"
            mar.load(path)
            return f"Aliases loaded from {path}"

        return (
            "Usage: /model-alias <subcommand>\n"
            "  add <alias> <model>  -- add an alias\n"
            "  remove <alias>       -- remove an alias\n"
            "  list                 -- list all aliases\n"
            "  resolve <name>       -- resolve alias to model\n"
            "  save [path]          -- save to JSON\n"
            "  load [path]          -- load from JSON"
        )

    registry.register(SlashCommand("model-alias", "Manage model aliases", model_alias_handler))
