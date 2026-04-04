"""Q283 CLI commands: /adapt-prompt, /rank-context, /select-examples, /style-match."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q283 slash commands."""

    async def adapt_prompt_handler(args: str) -> str:
        from lidco.adaptive.adapter import PromptAdapter

        adapter = _state.setdefault("adapter", PromptAdapter())
        parts = args.strip().split(maxsplit=1)
        if not parts:
            types = adapter.supported_types()
            return f"Supported types: {', '.join(types)}\nUsage: /adapt-prompt <task_type> <prompt>"

        task_type = parts[0]
        prompt = parts[1] if len(parts) > 1 else ""

        if not prompt:
            try:
                tpl = adapter.get_template(task_type)
                return f"Template for {task_type!r}:\n{tpl}"
            except KeyError:
                return f"Unknown task type: {task_type!r}. Use: {', '.join(adapter.supported_types())}"

        try:
            result = adapter.adapt(prompt, task_type)
            return result
        except KeyError:
            return f"Unknown task type: {task_type!r}. Use: {', '.join(adapter.supported_types())}"

    async def rank_context_handler(args: str) -> str:
        from lidco.adaptive.ranker import ContextRanker, ContextItem

        ranker = _state.setdefault("ranker", ContextRanker())
        parts = args.strip().split(maxsplit=1)
        if not parts:
            count = len(ranker.items())
            return f"Context items: {count}\nUsage: /rank-context <add text | rank query | clear>"

        subcmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if subcmd == "add":
            if not rest:
                return "Usage: /rank-context add <text>"
            ranker.add_item(ContextItem(text=rest))
            return f"Added context item ({len(ranker.items())} total)"

        if subcmd == "rank":
            if not rest:
                return "Usage: /rank-context rank <query>"
            items = ranker.items()
            if not items:
                return "No context items. Use /rank-context add <text> first."
            ranked = ranker.rank(items, rest)
            lines = [f"Ranked {len(ranked)} items for: {rest[:40]}"]
            for i, it in enumerate(ranked[:10], 1):
                score = ranker.score_item(it, rest)
                lines.append(f"  {i}. [{score:.3f}] {it.text[:60]}")
            return "\n".join(lines)

        if subcmd == "clear":
            ranker.clear()
            _state.pop("ranker", None)
            return "Context cleared."

        return "Usage: /rank-context <add text | rank query | clear>"

    async def select_examples_handler(args: str) -> str:
        from lidco.adaptive.selector import ExampleSelector, Example

        selector = _state.setdefault("selector", ExampleSelector())
        parts = args.strip().split(maxsplit=2)
        if not parts:
            count = len(selector.examples())
            return f"Examples: {count}\nUsage: /select-examples <add type input output | select type [k] | clear>"

        subcmd = parts[0].lower()

        if subcmd == "add":
            rest = args.strip()[4:].strip()  # everything after "add "
            tokens = rest.split("|")
            if len(tokens) < 3:
                return "Usage: /select-examples add <task_type> | <input> | <output>"
            task_type = tokens[0].strip()
            input_text = tokens[1].strip()
            output_text = tokens[2].strip()
            selector.add_example(Example(input_text=input_text, output_text=output_text, task_type=task_type))
            return f"Added example for {task_type!r} ({len(selector.examples())} total)"

        if subcmd == "select":
            rest_parts = args.strip().split()[1:]
            if not rest_parts:
                return "Usage: /select-examples select <task_type> [k]"
            task_type = rest_parts[0]
            k = int(rest_parts[1]) if len(rest_parts) > 1 else 3
            selected = selector.select(task_type, k=k)
            if not selected:
                return f"No examples found for {task_type!r}."
            lines = [f"Selected {len(selected)} examples for {task_type!r}:"]
            for i, ex in enumerate(selected, 1):
                lines.append(f"  {i}. [{ex.task_type}] {ex.input_text[:50]} -> {ex.output_text[:50]}")
            return "\n".join(lines)

        if subcmd == "clear":
            selector.clear()
            _state.pop("selector", None)
            return "Examples cleared."

        return "Usage: /select-examples <add | select | clear>"

    async def style_match_handler(args: str) -> str:
        from lidco.adaptive.style import StyleTransfer

        transfer = StyleTransfer()
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Usage: /style-match <analyze code | naming code | match code>"

        subcmd = parts[0].lower()
        code = parts[1] if len(parts) > 1 else ""

        if subcmd == "analyze":
            if not code:
                return "Usage: /style-match analyze <code>"
            profile = transfer.analyze(code)
            lines = [f"Style analysis:"]
            for key, val in profile.items():
                lines.append(f"  {key}: {val}")
            return "\n".join(lines)

        if subcmd == "naming":
            if not code:
                return "Usage: /style-match naming <code>"
            naming = transfer.detect_naming(code)
            return f"Detected naming: {naming}"

        if subcmd == "match":
            if not code:
                return "Usage: /style-match match <code>"
            style = transfer.analyze(code)
            converted = transfer.match(code, style)
            return f"Matched style ({style['naming']}):\n{converted}"

        return "Usage: /style-match <analyze | naming | match>"

    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("adapt-prompt", "Adapt prompt for task type", adapt_prompt_handler))
    registry.register(SlashCommand("rank-context", "Rank context by relevance", rank_context_handler))
    registry.register(SlashCommand("select-examples", "Select few-shot examples", select_examples_handler))
    registry.register(SlashCommand("style-match", "Detect and match coding style", style_match_handler))
