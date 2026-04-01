"""Q192 CLI commands: /output-style, /explanatory, /learning, /brief."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q192 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /output-style
    # ------------------------------------------------------------------

    async def output_style_handler(args: str) -> str:
        from lidco.output.style_registry import (
            BriefStyle,
            DefaultStyle,
            StyleRegistry,
        )

        reg: StyleRegistry | None = _state.get("style_registry")  # type: ignore[assignment]
        if reg is None:
            reg = StyleRegistry()
            reg = reg.register(DefaultStyle())
            reg = reg.register(BriefStyle())
            _state["style_registry"] = reg

        parts = args.strip().split()
        if not parts:
            styles = reg.list_styles()
            active = reg.active
            active_name = active.name if active else "(none)"
            return f"Output styles: {', '.join(styles)}\nActive: {active_name}"

        sub = parts[0].lower()
        if sub == "set" and len(parts) >= 2:
            name = parts[1]
            try:
                reg = reg.set_active(name)
                _state["style_registry"] = reg
                return f"Active style set to: {name}"
            except KeyError:
                return f"Unknown style: {name}"
        if sub == "list":
            styles = reg.list_styles()
            return f"Available styles: {', '.join(styles)}"
        return "Usage: /output-style [list | set <name>]"

    # ------------------------------------------------------------------
    # /explanatory
    # ------------------------------------------------------------------

    async def explanatory_handler(args: str) -> str:
        from lidco.output.explanatory import ExplanatoryStyle

        style = ExplanatoryStyle()
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Explanatory mode: transforms output with contextual reasoning."

        sub = parts[0].lower()
        if sub == "context" and len(parts) >= 2:
            return style.add_context(parts[1], "rationale")
        if sub == "explain" and len(parts) >= 2:
            return style.explain_choice(parts[1], ())
        if sub == "transform" and len(parts) >= 2:
            return style.transform(parts[1])
        return "Usage: /explanatory [context <text> | explain <choice> | transform <text>]"

    # ------------------------------------------------------------------
    # /learning
    # ------------------------------------------------------------------

    async def learning_handler(args: str) -> str:
        from lidco.output.learning import LearningStyle

        style = LearningStyle()
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Learning mode: adds quizzes, hints, and educational prompts."

        sub = parts[0].lower()
        if sub == "quiz" and len(parts) >= 2:
            quiz = style.generate_quiz(parts[1], "# example code")
            return f"Q: {quiz.question}\n" + "\n".join(
                f"  {i+1}. {o}" for i, o in enumerate(quiz.options)
            )
        if sub == "hint" and len(parts) >= 2:
            return style.progressive_hint(parts[1], 1)
        if sub == "transform" and len(parts) >= 2:
            return style.transform(parts[1])
        return "Usage: /learning [quiz <topic> | hint <problem> | transform <text>]"

    # ------------------------------------------------------------------
    # /brief
    # ------------------------------------------------------------------

    async def brief_handler(args: str) -> str:
        from lidco.output.style_registry import BriefStyle

        style = BriefStyle()
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Brief mode: strips blank lines and truncates long output."
        return style.transform(parts[1]) if len(parts) >= 2 else style.transform(parts[0])

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    registry.register(SlashCommand("output-style", "Manage output styles", output_style_handler))
    registry.register(SlashCommand("explanatory", "Explanatory output mode", explanatory_handler))
    registry.register(SlashCommand("learning", "Learning output mode", learning_handler))
    registry.register(SlashCommand("brief", "Brief output mode", brief_handler))
