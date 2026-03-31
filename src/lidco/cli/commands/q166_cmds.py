"""Q166 CLI commands: /flow, /intent."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def _get_components():
    """Lazily initialize and return (tracker, inferrer, hint_engine, state_manager)."""
    from lidco.flow.action_tracker import ActionTracker
    from lidco.flow.intent_inferrer import IntentInferrer
    from lidco.flow.hint_engine import HintEngine
    from lidco.flow.state_manager import FlowStateManager

    if "tracker" not in _state:
        tracker = ActionTracker()
        inferrer = IntentInferrer(tracker)
        _state["tracker"] = tracker
        _state["inferrer"] = inferrer
        _state["hint_engine"] = HintEngine(tracker, inferrer)
        _state["state_manager"] = FlowStateManager(tracker, inferrer)

    return (
        _state["tracker"],
        _state["inferrer"],
        _state["hint_engine"],
        _state["state_manager"],
    )


def register(registry) -> None:
    """Register Q166 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def flow_handler(args: str) -> str:
        tracker, inferrer, hint_engine, state_manager = _get_components()

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "status"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "status":
            return state_manager.summary()

        if sub == "history":
            limit = int(rest) if rest.isdigit() else 10
            actions = tracker.recent(limit=limit)
            if not actions:
                return "No actions recorded."
            lines = []
            for a in actions:
                status = "OK" if a.success else "FAIL"
                fp = f" [{a.file_path}]" if a.file_path else ""
                lines.append(f"  {a.action_type:8s} {status:4s} {a.detail}{fp}")
            return f"Recent actions ({len(actions)}):\n" + "\n".join(lines)

        if sub == "hints":
            limit = int(rest) if rest.isdigit() else 3
            hints = hint_engine.generate_hints(max_hints=limit)
            if not hints:
                return "No hints available."
            lines = []
            for h in hints:
                sug = f" -> {h.action_suggestion}" if h.action_suggestion else ""
                lines.append(f"  [P{h.priority}] {h.text}{sug}")
            return "Hints:\n" + "\n".join(lines)

        if sub == "clear":
            tracker.clear()
            return "Flow history cleared."

        if sub == "stats":
            s = tracker.stats()
            if not s:
                return "No actions recorded."
            return json.dumps(s, indent=2)

        return (
            "Usage: /flow [subcommand]\n"
            "  status   — show flow summary (default)\n"
            "  history  — recent action history\n"
            "  hints    — proactive suggestions\n"
            "  stats    — action type totals\n"
            "  clear    — clear flow history"
        )

    async def intent_handler(args: str) -> str:
        _, inferrer, _, _ = _get_components()
        return inferrer.explain()

    registry.register(SlashCommand("flow", "Flow tracking & smart suggestions", flow_handler))
    registry.register(SlashCommand("intent", "Show inferred developer intent", intent_handler))
