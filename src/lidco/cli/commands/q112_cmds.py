"""Q112 CLI commands: /todo /mode /spawn."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q112 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ #
    # /todo                                                                #
    # ------------------------------------------------------------------ #

    async def todo_handler(args: str) -> str:
        from lidco.tasks.live_todo import LiveTodoTracker, TodoItem, TodoStatus
        from lidco.tasks.planning_agent import TodoPlanningAgent

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_tracker() -> LiveTodoTracker:
            if "todo_tracker" not in _state:
                _state["todo_tracker"] = LiveTodoTracker()
            return _state["todo_tracker"]  # type: ignore[return-value]

        if sub == "plan":
            if not rest:
                rest = "Unnamed task"
            agent = TodoPlanningAgent()
            plan = agent.plan(rest)
            tracker = _get_tracker()
            plan_dicts = [
                {"id": item.id, "label": item.label, "depends_on": item.depends_on}
                for item in plan.items
            ]
            tracker.from_plan(plan_dicts)
            lines = [f"Plan created: {plan.description} ({len(plan.items)} steps)"]
            lines.append(tracker.render_ascii())
            return "\n".join(lines)

        if sub == "board":
            tracker = _get_tracker()
            board = tracker.render_ascii()
            if not board:
                return "Todo board is empty."
            return board

        if sub == "done":
            if not rest:
                return "Usage: /todo done <id>"
            tracker = _get_tracker()
            try:
                tracker.update(rest.strip(), TodoStatus.DONE)
                return f"Marked '{rest.strip()}' as done."
            except KeyError:
                return f"Item not found: {rest.strip()}"

        if sub == "block":
            tokens = rest.split(maxsplit=1)
            if not tokens:
                return "Usage: /todo block <id> <reason>"
            item_id = tokens[0]
            reason = tokens[1] if len(tokens) > 1 else "no reason given"
            tracker = _get_tracker()
            try:
                tracker.update(item_id, TodoStatus.BLOCKED, blocked_reason=reason)
                return f"Marked '{item_id}' as blocked: {reason}"
            except KeyError:
                return f"Item not found: {item_id}"

        if sub == "clear":
            tracker = _get_tracker()
            tracker.clear()
            return "Todo board cleared."

        return (
            "Usage: /todo <sub>\n"
            "  plan <description>     -- create a plan from description\n"
            "  board                  -- show current todo board\n"
            "  done <id>              -- mark item as done\n"
            "  block <id> <reason>    -- mark item as blocked\n"
            "  clear                  -- clear the board"
        )

    # ------------------------------------------------------------------ #
    # /mode                                                                #
    # ------------------------------------------------------------------ #

    async def mode_handler(args: str) -> str:
        from lidco.composer.chat_mode import ChatModeManager

        def _get_manager() -> ChatModeManager:
            if "chat_mode_manager" not in _state:
                _state["chat_mode_manager"] = ChatModeManager()
            return _state["chat_mode_manager"]  # type: ignore[return-value]

        stripped = args.strip().lower()

        if not stripped:
            return (
                "Usage: /mode <code|ask|architect|help>\n"
                "  status  -- show current mode"
            )

        if stripped == "status":
            mgr = _get_manager()
            return f"Current mode: {mgr.active_mode.value}"

        mgr = _get_manager()
        try:
            transition = mgr.switch(stripped)
            msg = f"Switched to {transition.to_mode.value} mode."
            if transition.warning:
                msg += f"\nWarning: {transition.warning}"
            return msg
        except ValueError:
            return f"Invalid mode: {stripped}. Choose from: code, ask, architect, help"

    # ------------------------------------------------------------------ #
    # /spawn                                                               #
    # ------------------------------------------------------------------ #

    async def spawn_handler(args: str) -> str:
        from lidco.agents.child_session import ChildSessionSpawner

        prompt = args.strip()
        if not prompt:
            return "Usage: /spawn <prompt>"

        spawner = ChildSessionSpawner()
        handle = spawner.spawn(prompt)
        return (
            f"Child session spawned (dry-run):\n"
            f"  Session ID: {handle.session_id}\n"
            f"  Prompt: {handle.prompt}"
        )

    registry.register(SlashCommand("todo", "Live todo board & planning", todo_handler))
    registry.register(SlashCommand("mode", "Switch chat mode", mode_handler))
    registry.register(SlashCommand("spawn", "Spawn child session", spawn_handler))
