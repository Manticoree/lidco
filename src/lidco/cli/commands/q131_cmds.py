"""Q131 CLI commands: /prompt."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def _split_json_and_rest(text: str) -> tuple[str, str]:
    """Extract the first complete JSON value from *text*, return (json_str, rest).

    Scans for matching brackets/braces to handle spaces inside JSON.
    """
    text = text.strip()
    if not text:
        return "", ""
    opener = text[0]
    closer = {"{": "}", "[": "]"}.get(opener)
    if closer is None:
        # Not a JSON object/array — fall back to simple split
        parts = text.split(maxsplit=1)
        return parts[0], parts[1] if len(parts) > 1 else ""
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[: i + 1], text[i + 1:].lstrip()
    return text, ""


def register(registry) -> None:
    """Register Q131 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def prompt_handler(args: str) -> str:
        from lidco.prompts.template_engine import PromptTemplateEngine, RenderContext
        from lidco.prompts.prompt_builder import PromptBuilder
        from lidco.prompts.few_shot import FewShotSelector, FewShotExample
        from lidco.prompts.chain_builder import PromptChain, ChainStep

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "render":
            # /prompt render <json_vars> <template>
            json_str, template = _split_json_and_rest(rest)
            if not json_str or not template:
                return "Usage: /prompt render <json_vars> <template>"
            try:
                variables = json.loads(json_str)
            except json.JSONDecodeError:
                return "Invalid JSON variables."
            engine = PromptTemplateEngine()
            return engine.render_dict(template, variables)

        if sub == "build":
            # /prompt build <json_messages>
            if not rest:
                return "Usage: /prompt build <json_messages>"
            try:
                messages = json.loads(rest)
            except json.JSONDecodeError:
                return "Invalid JSON messages."
            builder = PromptBuilder()
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    builder.system(content)
                elif role == "assistant":
                    builder.assistant(content)
                else:
                    builder.user(content)
            return builder.build()

        if sub == "examples":
            # /prompt examples <json_pairs>
            if not rest:
                return "Usage: /prompt examples <json_pairs>"
            try:
                pairs = json.loads(rest)
            except json.JSONDecodeError:
                return "Invalid JSON pairs."
            selector = FewShotSelector()
            selector.load_from_dict(pairs)
            examples = selector.select("", n=len(pairs))
            return selector.format(examples, style="qa")

        if sub == "chain":
            # /prompt chain <json_steps> <json_vars>
            steps_str, vars_str = _split_json_and_rest(rest)
            if not steps_str or not vars_str:
                return "Usage: /prompt chain <json_steps> <json_vars>"
            try:
                steps_data = json.loads(steps_str)
                variables = json.loads(vars_str)
            except json.JSONDecodeError:
                return "Invalid JSON input."
            chain = PromptChain()
            for s in steps_data:
                chain.add_step(
                    ChainStep(
                        name=s.get("name", "step"),
                        template=s.get("template", ""),
                        output_key=s.get("output_key", "result"),
                        stop_if_empty=s.get("stop_if_empty", False),
                    )
                )
            result = chain.run(variables, execute_fn=lambda p: f"[result for: {p[:40]}]")
            lines = [f"Steps run: {result.steps_run}"]
            for k, v in result.outputs.items():
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)

        return (
            "Usage: /prompt <sub>\n"
            "  render <json_vars> <template>  -- render template\n"
            "  build <json_messages>          -- build prompt from messages\n"
            "  examples <json_pairs>          -- format few-shot examples\n"
            "  chain <json_steps> <json_vars> -- run prompt chain"
        )

    registry.register(SlashCommand("prompt", "Prompt engineering toolkit (Q131)", prompt_handler))
