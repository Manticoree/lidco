"""Q119 CLI commands: /rules, /effort, /color."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q119 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ #
    # /rules                                                               #
    # ------------------------------------------------------------------ #

    async def rules_handler(args: str) -> str:
        from lidco.rules.rules_loader import RulesFileLoader
        from lidco.rules.rules_resolver import RulesResolver

        loader = _state.get("rules_loader") or RulesFileLoader()
        resolver = RulesResolver(loader)  # type: ignore[arg-type]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "list":
            rules = loader.load_all()
            if not rules:
                return "No rules files found."
            lines = ["Rules files:"]
            for r in rules:
                name = r.path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                lines.append(f"  {name}  glob={r.glob_pattern}")
            return "\n".join(lines)

        if sub == "check":
            rest = parts[1].strip() if len(parts) > 1 else ""
            if not rest:
                return "Usage: /rules check <file>"
            matched = resolver.resolve([rest])
            if not matched:
                return f"No rules match '{rest}'."
            lines = [f"Rules matching '{rest}':"]
            for r in matched:
                name = r.path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                lines.append(f"  {name}  glob={r.glob_pattern}")
            return "\n".join(lines)

        return "Usage: /rules [list | check <file>]"

    registry.register(SlashCommand("rules", "List and check rules files", rules_handler))

    # ------------------------------------------------------------------ #
    # /effort                                                              #
    # ------------------------------------------------------------------ #

    async def effort_handler(args: str) -> str:
        from lidco.config.effort_manager import EffortManager, EffortLevel

        if "effort_manager" not in _state:
            _state["effort_manager"] = EffortManager()

        mgr: EffortManager = _state["effort_manager"]  # type: ignore[assignment]

        parts = args.strip().split()
        sub = parts[0].lower() if parts else ""

        if not sub:
            # Show current
            level = mgr.level
            budget = mgr.get_budget()
            return (
                f"Effort: {level.value}  |  "
                f"max_tokens={budget.max_tokens}  thinking_tokens={budget.thinking_tokens}  "
                f"temperature={budget.temperature}"
            )

        if sub == "auto":
            word_count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 25
            selected = mgr.auto_select(word_count)
            mgr.set_level(selected)
            budget = mgr.get_budget()
            return (
                f"Auto-selected: {selected.value}  |  "
                f"max_tokens={budget.max_tokens}  thinking_tokens={budget.thinking_tokens}  "
                f"temperature={budget.temperature}"
            )

        # Set level
        try:
            budget = mgr.set_level(sub)
            return (
                f"Effort set to: {mgr.level.value}  |  "
                f"max_tokens={budget.max_tokens}  thinking_tokens={budget.thinking_tokens}  "
                f"temperature={budget.temperature}"
            )
        except ValueError:
            return f"Invalid effort level: '{sub}'. Choose: low, medium, high, auto."

    registry.register(SlashCommand("effort", "Manage effort level and token budgets", effort_handler))

    # ------------------------------------------------------------------ #
    # /color                                                               #
    # ------------------------------------------------------------------ #

    async def color_handler(args: str) -> str:
        from lidco.config.session_color import SessionColorManager, NAMED_COLORS, ColorError

        if "color_manager" not in _state:
            _state["color_manager"] = SessionColorManager()

        mgr: SessionColorManager = _state["color_manager"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0] if parts else ""

        if not sub:
            current = mgr.get_color()
            if current is None:
                return "No color set. Use /color <name|hex> to set one."
            return f"Current color: {current}"

        if sub.lower() == "reset":
            mgr.clear_color()
            return "Color reset."

        if sub.lower() == "list":
            names = sorted(NAMED_COLORS.keys())
            return "Available colors:\n  " + "  ".join(names)

        try:
            mgr.set_color(sub)
            return f"Color set to: {sub}"
        except ColorError:
            return f"Error: unknown color '{sub}'. Use a named color or #RRGGBB hex."

    registry.register(SlashCommand("color", "Set session terminal color", color_handler))
