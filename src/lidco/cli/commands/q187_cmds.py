"""Q187 CLI commands: /hookify, /hookify-list, /hookify-analyze, /hookify-test."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q187 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /hookify — add a new rule
    # ------------------------------------------------------------------

    async def hookify_handler(args: str) -> str:
        from lidco.hookify.engine import HookifyEngine
        from lidco.hookify.rule import ActionType, EventType, HookifyRule

        parts = args.strip().split(maxsplit=4)
        if len(parts) < 5:
            return "Usage: /hookify <name> <event_type> <pattern> <action> <message>"
        name, evt_str, pattern, act_str, message = parts
        try:
            event_type = EventType(evt_str.lower())
        except ValueError:
            return f"Invalid event_type: {evt_str}. Use: bash, file, stop, prompt, all"
        try:
            action = ActionType(act_str.lower())
        except ValueError:
            return f"Invalid action: {act_str}. Use: warn, block"
        rule = HookifyRule(
            name=name,
            event_type=event_type,
            pattern=pattern,
            action=action,
            message=message,
        )
        engine = _state.get("engine")
        if not isinstance(engine, HookifyEngine):
            engine = HookifyEngine()
        engine = engine.add_rule(rule)
        _state["engine"] = engine
        return f"Rule '{name}' added ({action.value} on {event_type.value})"

    registry.register(SlashCommand("hookify", "Add a hookify rule", hookify_handler))

    # ------------------------------------------------------------------
    # /hookify-list — list all rules
    # ------------------------------------------------------------------

    async def hookify_list_handler(args: str) -> str:
        from lidco.hookify.engine import HookifyEngine

        engine = _state.get("engine")
        if not isinstance(engine, HookifyEngine) or not engine.rules:
            return "No hookify rules defined."
        lines: list[str] = []
        for r in engine.rules:
            status = "enabled" if r.enabled else "disabled"
            lines.append(f"  {r.name}: {r.action.value} on {r.event_type.value} [{status}] — {r.pattern}")
        return "Hookify rules:\n" + "\n".join(lines)

    registry.register(SlashCommand("hookify-list", "List hookify rules", hookify_list_handler))

    # ------------------------------------------------------------------
    # /hookify-analyze — analyze conversation for suggestions
    # ------------------------------------------------------------------

    async def hookify_analyze_handler(args: str) -> str:
        from lidco.hookify.analyzer import ConversationAnalyzer

        analyzer = ConversationAnalyzer()
        history = _state.get("conversation_history")
        if not isinstance(history, list) or not history:
            return "No conversation history to analyze."
        suggestions = analyzer.analyze(history)
        if not suggestions:
            return "No rule suggestions found."
        lines: list[str] = []
        for s in suggestions:
            lines.append(f"  {s.name}: {s.action.value} on {s.event_type.value} (confidence: {s.confidence:.0%})")
        return "Suggested rules:\n" + "\n".join(lines)

    registry.register(SlashCommand("hookify-analyze", "Analyze conversation for rule suggestions", hookify_analyze_handler))

    # ------------------------------------------------------------------
    # /hookify-test — test rules against content
    # ------------------------------------------------------------------

    async def hookify_test_handler(args: str) -> str:
        from lidco.hookify.engine import HookifyEngine
        from lidco.hookify.rule import EventType

        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /hookify-test <event_type> <content>"
        evt_str, content = parts
        try:
            event_type = EventType(evt_str.lower())
        except ValueError:
            return f"Invalid event_type: {evt_str}"
        engine = _state.get("engine")
        if not isinstance(engine, HookifyEngine):
            return "No hookify rules defined."
        matches = engine.evaluate(event_type, content)
        if not matches:
            return "No rules matched."
        lines: list[str] = []
        for m in matches:
            lines.append(f"  {m.rule.name} ({m.rule.action.value}): matched '{m.matched_text}'")
        return "Matches:\n" + "\n".join(lines)

    registry.register(SlashCommand("hookify-test", "Test hookify rules against content", hookify_test_handler))
