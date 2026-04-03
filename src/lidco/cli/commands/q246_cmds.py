"""Q246 CLI commands: /prompt-optimize, /system-prompt, /few-shot, /prompt-debug."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q246 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /prompt-optimize
    # ------------------------------------------------------------------

    async def prompt_optimize_handler(args: str) -> str:
        from lidco.prompts.optimizer import PromptOptimizer

        if "optimizer" not in _state:
            _state["optimizer"] = PromptOptimizer()

        opt: PromptOptimizer = _state["optimizer"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            if not rest:
                return "Usage: /prompt-optimize add <prompt text>"
            vid = opt.add_variant(rest)
            return f"Added variant {vid}"

        if sub == "score":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /prompt-optimize score <id> <score>"
            try:
                score = float(tokens[1])
            except ValueError:
                return "Score must be a number."
            opt.record_score(tokens[0], score)
            return f"Recorded score {score} for {tokens[0]}"

        if sub == "best":
            b = opt.best()
            if b is None:
                return "No scored variants."
            return f"Best: {b.id} (score={b.score:.2f}) — {b.prompt[:80]}"

        if sub == "select":
            s = opt.select()
            if s is None:
                return "No variants available."
            return f"Selected: {s.id} — {s.prompt[:80]}"

        if sub == "list":
            variants = opt.list_variants()
            if not variants:
                return "No variants."
            lines = [f"{len(variants)} variant(s):"]
            for v in variants:
                lines.append(f"  {v.id} score={v.score:.2f} uses={v.uses}")
            return "\n".join(lines)

        if sub == "remove":
            if not rest:
                return "Usage: /prompt-optimize remove <id>"
            removed = opt.remove_variant(rest)
            return f"Removed {rest}" if removed else f"Variant '{rest}' not found."

        if sub == "stats":
            return json.dumps(opt.stats(), indent=2)

        return (
            "Usage: /prompt-optimize <subcommand>\n"
            "  add <text>       — add a prompt variant\n"
            "  score <id> <n>   — record a score\n"
            "  best             — show best variant\n"
            "  select           — weighted random pick\n"
            "  list             — list all variants\n"
            "  remove <id>      — remove a variant\n"
            "  stats            — summary statistics"
        )

    # ------------------------------------------------------------------
    # /system-prompt
    # ------------------------------------------------------------------

    async def system_prompt_handler(args: str) -> str:
        from lidco.prompts.system_builder import SystemPromptBuilder

        if "builder" not in _state:
            _state["builder"] = SystemPromptBuilder()

        builder: SystemPromptBuilder = _state["builder"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "add":
            if len(parts) < 3:
                return "Usage: /system-prompt add <name> <content>"
            name = parts[1]
            content = parts[2]
            builder.add_section(name, content)
            return f"Added section '{name}'"

        if sub == "remove":
            name = parts[1] if len(parts) > 1 else ""
            if not name:
                return "Usage: /system-prompt remove <name>"
            removed = builder.remove_section(name)
            return f"Removed '{name}'" if removed else f"Section '{name}' not found."

        if sub == "var":
            if len(parts) < 3:
                return "Usage: /system-prompt var <key> <value>"
            builder.set_variable(parts[1], parts[2])
            return f"Set variable '{parts[1]}'"

        if sub == "build":
            budget = None
            if len(parts) > 1:
                try:
                    budget = int(parts[1])
                except ValueError:
                    pass
            result = builder.build(token_budget=budget)
            return result if result else "(empty prompt)"

        if sub == "sections":
            secs = builder.sections()
            if not secs:
                return "No sections."
            lines = [f"{len(secs)} section(s):"]
            for s in secs:
                lines.append(f"  {s['name']} (priority={s['priority']}, len={s['length']})")
            return "\n".join(lines)

        if sub == "tokens":
            return f"Estimated tokens: {builder.token_estimate()}"

        return (
            "Usage: /system-prompt <subcommand>\n"
            "  add <name> <content>  — add a section\n"
            "  remove <name>         — remove a section\n"
            "  var <key> <value>     — set a variable\n"
            "  build [budget]        — build the prompt\n"
            "  sections              — list sections\n"
            "  tokens                — token estimate"
        )

    # ------------------------------------------------------------------
    # /few-shot
    # ------------------------------------------------------------------

    async def few_shot_handler(args: str) -> str:
        from lidco.prompts.few_shot_manager import FewShotManager

        if "few_shot" not in _state:
            _state["few_shot"] = FewShotManager()

        mgr: FewShotManager = _state["few_shot"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            # Expect "input | output [| tag1,tag2]"
            segments = [s.strip() for s in rest.split("|")]
            if len(segments) < 2:
                return "Usage: /few-shot add <input> | <output> [| tag1,tag2]"
            inp = segments[0]
            out = segments[1]
            tags = [t.strip() for t in segments[2].split(",")] if len(segments) > 2 else None
            eid = mgr.add_example(inp, out, tags)
            return f"Added example {eid}"

        if sub == "remove":
            if not rest:
                return "Usage: /few-shot remove <id>"
            removed = mgr.remove_example(rest)
            return f"Removed {rest}" if removed else f"Example '{rest}' not found."

        if sub == "select":
            if not rest:
                return "Usage: /few-shot select <query>"
            examples = mgr.select(rest)
            if not examples:
                return "No examples matched."
            return mgr.format_examples(examples)

        if sub == "list":
            examples = mgr.list_examples()
            if not examples:
                return "No examples."
            lines = [f"{len(examples)} example(s):"]
            for ex in examples:
                tag_str = f" [{', '.join(ex.tags)}]" if ex.tags else ""
                lines.append(f"  {ex.id}: {ex.input[:40]}...{tag_str}")
            return "\n".join(lines)

        return (
            "Usage: /few-shot <subcommand>\n"
            "  add <input> | <output> [| tags]  — add an example\n"
            "  remove <id>                       — remove an example\n"
            "  select <query>                    — select relevant examples\n"
            "  list                              — list all examples"
        )

    # ------------------------------------------------------------------
    # /prompt-debug
    # ------------------------------------------------------------------

    async def prompt_debug_handler(args: str) -> str:
        from lidco.prompts.debugger import PromptDebugger

        if "debugger" not in _state:
            _state["debugger"] = PromptDebugger()

        dbg: PromptDebugger = _state["debugger"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "record":
            # "record <prompt> | <response>"
            rest = parts[1] if len(parts) > 1 else ""
            if len(parts) > 2:
                rest = parts[1] + " " + parts[2]
            segments = [s.strip() for s in rest.split("|", 1)]
            if len(segments) < 2:
                return "Usage: /prompt-debug record <prompt> | <response>"
            dbg.record_turn(segments[0], segments[1])
            return f"Recorded turn {len(dbg._turns) - 1}"

        if sub == "show":
            idx_str = parts[1] if len(parts) > 1 else ""
            try:
                idx = int(idx_str)
            except ValueError:
                return "Usage: /prompt-debug show <turn>"
            info = dbg.show_turn(idx)
            if info is None:
                return f"Turn {idx} not found."
            return json.dumps(info, indent=2)

        if sub == "diff":
            if len(parts) < 3:
                return "Usage: /prompt-debug diff <turn_a> <turn_b>"
            try:
                a, b = int(parts[1]), int(parts[2])
            except ValueError:
                return "Turn indices must be integers."
            lines = dbg.diff(a, b)
            return "\n".join(lines)

        if sub == "tokens":
            idx_str = parts[1] if len(parts) > 1 else ""
            try:
                idx = int(idx_str)
            except ValueError:
                return "Usage: /prompt-debug tokens <turn>"
            bd = dbg.token_breakdown(idx)
            if not bd:
                return f"Turn {idx} not found."
            return json.dumps(bd, indent=2)

        if sub == "history":
            h = dbg.history()
            if not h:
                return "No turns recorded."
            lines = [f"{len(h)} turn(s):"]
            for t in h:
                lines.append(f"  turn {t['turn']}: prompt={t['prompt_len']}c response={t['response_len']}c tokens={t['tokens']['total']}")
            return "\n".join(lines)

        if sub == "highlight":
            if len(parts) < 3:
                return "Usage: /prompt-debug highlight <turn> <marker1,marker2,...>"
            try:
                idx = int(parts[1])
            except ValueError:
                return "Turn index must be an integer."
            markers = [m.strip() for m in parts[2].split(",")]
            result = dbg.highlight_injected(idx, markers)
            return result if result else f"Turn {idx} not found."

        return (
            "Usage: /prompt-debug <subcommand>\n"
            "  record <prompt> | <response>  — record a turn\n"
            "  show <turn>                   — show turn details\n"
            "  diff <a> <b>                  — diff two turns\n"
            "  tokens <turn>                 — token breakdown\n"
            "  history                       — list all turns\n"
            "  highlight <turn> <markers>    — highlight injections"
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    registry.register(SlashCommand("prompt-optimize", "Prompt A/B testing and variant management", prompt_optimize_handler))
    registry.register(SlashCommand("system-prompt", "Build and manage system prompts", system_prompt_handler))
    registry.register(SlashCommand("few-shot", "Manage few-shot examples", few_shot_handler))
    registry.register(SlashCommand("prompt-debug", "Debug and inspect prompt turns", prompt_debug_handler))
