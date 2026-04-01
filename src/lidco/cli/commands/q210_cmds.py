"""Q210 CLI commands: /pair, /explain-code, /suggest, /complete."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q210 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /pair
    # ------------------------------------------------------------------

    async def pair_handler(args: str) -> str:
        from lidco.pairing.collaborative_editor import CollaborativeEditor, EditOperation

        if "editor" not in _state:
            _state["editor"] = CollaborativeEditor()
        editor: CollaborativeEditor = _state["editor"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "init":
            content = parts[1] if len(parts) > 1 else ""
            _state["editor"] = CollaborativeEditor(initial_content=content)
            return f"Collaborative editor initialized ({len(content)} chars)."

        if sub == "insert":
            if len(parts) < 3:
                return "Usage: /pair insert <position> <text>"
            try:
                pos = int(parts[1])
            except ValueError:
                return "Position must be an integer."
            text = parts[2] if len(parts) > 2 else ""
            op = EditOperation(user_id="user", op_type="insert", position=pos, content=text)
            state = editor.apply(op)
            return f"Inserted at {pos}. Version: {state.version}. Content: {state.content!r}"

        if sub == "state":
            state = editor.get_state()
            return f"Version: {state.version}\nContent: {state.content!r}\nParticipants: {editor.participants()}"

        if sub == "undo":
            result = editor.undo("user")
            if result is None:
                return "Nothing to undo."
            return f"Undo complete. Version: {result.version}. Content: {result.content!r}"

        return (
            "Usage: /pair <subcommand>\n"
            "  init [content]       — initialize editor\n"
            "  insert <pos> <text>  — insert text\n"
            "  state                — show current state\n"
            "  undo                 — undo last operation"
        )

    # ------------------------------------------------------------------
    # /explain-code
    # ------------------------------------------------------------------

    async def explain_code_handler(args: str) -> str:
        from lidco.pairing.code_explainer import CodeExplainer, DetailLevel

        if "explainer" not in _state:
            _state["explainer"] = CodeExplainer()
        explainer: CodeExplainer = _state["explainer"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        level_str = parts[0].lower() if parts else "brief"
        code = parts[1] if len(parts) > 1 else ""

        if not code:
            return "Usage: /explain-code [brief|detailed|eli5] <code>"

        level_map = {
            "brief": DetailLevel.BRIEF,
            "detailed": DetailLevel.DETAILED,
            "eli5": DetailLevel.ELI5,
        }
        level = level_map.get(level_str, DetailLevel.BRIEF)
        if level_str not in level_map:
            code = args.strip()

        explanation = explainer.explain(code, level)
        lines = [f"Level: {explanation.level.value}", f"Summary: {explanation.summary}"]
        if explanation.complexity_note:
            lines.append(f"Complexity: {explanation.complexity_note}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /suggest
    # ------------------------------------------------------------------

    async def suggest_handler(args: str) -> str:
        from lidco.pairing.suggestion_stream import SuggestionStream

        if "stream" not in _state:
            _state["stream"] = SuggestionStream()
        stream: SuggestionStream = _state["stream"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "generate":
            suggestions = stream.generate(prompt=rest)
            if not suggestions:
                return "No suggestions. Add context first with /suggest context <file> <code>."
            lines = [f"{len(suggestions)} suggestion(s):"]
            for i, s in enumerate(suggestions):
                lines.append(f"  [{i}] {s.type.value}: {s.content!r} (confidence={s.confidence:.1f})")
            return "\n".join(lines)

        if sub == "context":
            stream.add_context(file=rest or "untitled.py", content=rest, cursor_line=0)
            return f"Context added for '{rest or 'untitled.py'}'."

        if sub == "accept":
            try:
                idx = int(rest)
            except ValueError:
                return "Usage: /suggest accept <index>"
            result = stream.accept(idx)
            if result is None:
                return "Invalid suggestion index."
            return f"Accepted: {result.content!r}"

        if sub == "clear":
            stream.clear()
            return "Suggestions cleared."

        return (
            "Usage: /suggest <subcommand>\n"
            "  context <file> <code> — add context\n"
            "  generate [prompt]     — generate suggestions\n"
            "  accept <index>        — accept a suggestion\n"
            "  clear                 — clear all"
        )

    # ------------------------------------------------------------------
    # /complete
    # ------------------------------------------------------------------

    async def complete_handler(args: str) -> str:
        from lidco.pairing.completion_provider import CompletionProvider

        if "provider" not in _state:
            _state["provider"] = CompletionProvider()
        provider: CompletionProvider = _state["provider"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "prefix":
            items = provider.complete(rest)
            if not items:
                return f"No completions for '{rest}'."
            lines = [f"{len(items)} completion(s):"]
            for item in items:
                lines.append(f"  {item.label} ({item.kind}) — {item.detail}")
            return "\n".join(lines)

        if sub == "import":
            items = provider.complete_import(rest)
            if not items:
                return f"No import completions for '{rest}'."
            lines = [f"{len(items)} import completion(s):"]
            for item in items:
                lines.append(f"  {item.insert_text}")
            return "\n".join(lines)

        if sub == "attr":
            attr_parts = rest.split(maxsplit=1)
            obj_type = attr_parts[0] if attr_parts else ""
            prefix = attr_parts[1] if len(attr_parts) > 1 else ""
            items = provider.complete_attribute(obj_type, prefix)
            if not items:
                return f"No attribute completions for '{obj_type}'."
            lines = [f"{len(items)} attribute completion(s):"]
            for item in items:
                lines.append(f"  {item.label} — {item.detail}")
            return "\n".join(lines)

        return (
            "Usage: /complete <subcommand>\n"
            "  prefix <text>           — complete prefix\n"
            "  import <partial>        — complete import\n"
            "  attr <type> [prefix]    — complete attribute"
        )

    registry.register(SlashCommand("pair", "Collaborative pair programming editor", pair_handler))
    registry.register(SlashCommand("explain-code", "Explain code at various detail levels", explain_code_handler))
    registry.register(SlashCommand("suggest", "AI code suggestions", suggest_handler))
    registry.register(SlashCommand("complete", "Context-aware code completions", complete_handler))
