"""Q244 CLI commands: /replay, /inspect-message, /profile-conversation, /assert."""
from __future__ import annotations

# Module-level shared state (accessible from tests)
_state: dict = {}


def _get_state() -> dict:
    return _state


def _truncate(text: str | None, max_len: int = 80) -> str:
    if not text:
        return "(empty)"
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def register(registry) -> None:
    """Register Q244 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /replay
    # ------------------------------------------------------------------

    async def replay_handler(args: str) -> str:
        from lidco.conversation.replay_engine import ReplayEngine

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        state = _get_state()
        engine: ReplayEngine | None = state.get("replay_engine")

        if sub == "load":
            import json
            try:
                messages = json.loads(rest) if rest else []
            except json.JSONDecodeError:
                return "Error: invalid JSON"
            state["replay_engine"] = ReplayEngine(messages)
            return f"Loaded {len(messages)} messages."

        if engine is None:
            return "No conversation loaded. Use: /replay load <json>"

        if sub == "forward":
            msg = engine.step_forward()
            if msg is None:
                return "End of conversation."
            return f"Turn {engine.current_turn}: {msg.get('role', '?')} — {_truncate(msg.get('content', ''))}"

        if sub == "backward":
            msg = engine.step_backward()
            if msg is None:
                return "At beginning of conversation."
            return f"Turn {engine.current_turn}: {msg.get('role', '?')} — {_truncate(msg.get('content', ''))}"

        if sub == "jump":
            turn = int(rest) if rest else 0
            msg = engine.jump_to(turn)
            if msg is None:
                return f"Invalid turn: {turn}"
            return f"Turn {turn}: {msg.get('role', '?')} — {_truncate(msg.get('content', ''))}"

        if sub == "status":
            return f"Turn {engine.current_turn} / {engine.total_turns}"

        if sub == "reset":
            engine.reset()
            return "Replay reset."

        return (
            "Usage: /replay <subcommand>\n"
            "  load <json>    — load conversation messages\n"
            "  forward        — step forward\n"
            "  backward       — step backward\n"
            "  jump <turn>    — jump to turn\n"
            "  status         — show current position\n"
            "  reset          — reset to beginning"
        )

    # ------------------------------------------------------------------
    # /inspect-message
    # ------------------------------------------------------------------

    async def inspect_message_handler(args: str) -> str:
        from lidco.conversation.debug_inspector import DebugInspector

        import json
        text = args.strip()
        if not text:
            return "Usage: /inspect-message <json message>"
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            return "Error: invalid JSON"

        inspector = DebugInspector()
        info = inspector.inspect(message)
        tokens = inspector.token_estimate(message)
        lines = [
            f"Role: {info.role}",
            f"Content length: {info.content_length}",
            f"Has content: {info.has_content}",
            f"Tool calls: {info.tool_call_count}",
            f"Est. tokens: {tokens}",
        ]
        if info.metadata:
            lines.append(f"Metadata keys: {', '.join(info.metadata.keys())}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /profile-conversation
    # ------------------------------------------------------------------

    async def profile_conversation_handler(args: str) -> str:
        from lidco.conversation.profiler import ConversationProfiler

        import json
        text = args.strip()
        if not text:
            return "Usage: /profile-conversation <json messages>"
        try:
            messages = json.loads(text)
        except json.JSONDecodeError:
            return "Error: invalid JSON"

        profiler = ConversationProfiler(messages)
        return profiler.summary()

    # ------------------------------------------------------------------
    # /assert
    # ------------------------------------------------------------------

    async def assert_handler(args: str) -> str:
        from lidco.conversation.assertions import AssertionEngine

        import json
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        state = _get_state()
        engine = state.get("replay_engine")

        if sub == "load":
            try:
                messages = json.loads(rest) if rest else []
            except json.JSONDecodeError:
                return "Error: invalid JSON"
            state["assert_messages"] = messages
            return f"Loaded {len(messages)} messages for assertions."

        messages = state.get("assert_messages", [])
        if not messages and engine is not None:
            from lidco.conversation.replay_engine import ReplayEngine
            if isinstance(engine, ReplayEngine):
                messages = engine._messages

        if not messages:
            return "No messages loaded. Use: /assert load <json>"

        ae = AssertionEngine(messages)

        if sub == "contains":
            p = rest.split(maxsplit=1)
            turn = int(p[0]) if p else 0
            text = p[1] if len(p) > 1 else ""
            result = ae.assert_contains(turn, text)
            return f"PASS" if result else "FAIL"

        if sub == "role":
            p = rest.split()
            turn = int(p[0]) if p else 0
            role = p[1] if len(p) > 1 else ""
            result = ae.assert_role(turn, role)
            return "PASS" if result else "FAIL"

        if sub == "no-empty":
            passed, indices = ae.assert_no_empty_turns()
            if passed:
                return "PASS: no empty turns"
            return f"FAIL: empty turns at {indices}"

        if sub == "run":
            try:
                assertion_list = json.loads(rest) if rest else []
            except json.JSONDecodeError:
                return "Error: invalid JSON"
            results = ae.run_all(assertion_list)
            lines = []
            for r in results:
                status = "PASS" if r.passed else "FAIL"
                lines.append(f"{status}: {r.assertion} — {r.details}")
            return "\n".join(lines) if lines else "No assertions provided."

        return (
            "Usage: /assert <subcommand>\n"
            "  load <json>            — load messages\n"
            "  contains <turn> <text> — check content\n"
            "  role <turn> <role>     — check role\n"
            "  no-empty               — check for empty turns\n"
            "  run <json assertions>  — run assertion batch"
        )

    registry.register(SlashCommand("replay", "Conversation replay navigator", replay_handler))
    registry.register(SlashCommand("inspect-message", "Inspect a conversation message", inspect_message_handler))
    registry.register(SlashCommand("profile-conversation", "Profile conversation token usage", profile_conversation_handler))
    registry.register(SlashCommand("assert", "Conversation assertions", assert_handler))
