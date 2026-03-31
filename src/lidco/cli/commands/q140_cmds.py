"""Q140 CLI commands: /input."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q140 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def input_handler(args: str) -> str:
        from lidco.input.arg_parser import ArgParser
        from lidco.input.did_you_mean import DidYouMean
        from lidco.input.help_formatter import HelpFormatter, CommandHelp
        from lidco.input.sanitizer import InputSanitizer

        if "sanitizer" not in _state:
            _state["sanitizer"] = InputSanitizer()
        if "dym" not in _state:
            _state["dym"] = DidYouMean([])
        if "formatter" not in _state:
            _state["formatter"] = HelpFormatter()

        sanitizer: InputSanitizer = _state["sanitizer"]  # type: ignore[assignment]
        dym: DidYouMean = _state["dym"]  # type: ignore[assignment]
        formatter: HelpFormatter = _state["formatter"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "parse":
            sub_parts = rest.split(maxsplit=1)
            cmd_name = sub_parts[0] if sub_parts else "cmd"
            parse_str = sub_parts[1] if len(sub_parts) > 1 else ""
            parser = ArgParser(cmd_name)
            result = parser.parse(parse_str)
            return json.dumps(
                {
                    "positional": result.positional,
                    "flags": result.flags,
                    "options": result.options,
                    "errors": result.errors,
                },
                indent=2,
            )

        if sub == "suggest":
            if not rest:
                return "Usage: /input suggest <command>"
            # Populate from registry commands if available
            if hasattr(registry, "_commands"):
                known = list(registry._commands.keys())
                _state["dym"] = DidYouMean(known)
                dym = _state["dym"]  # type: ignore[assignment]
            return dym.format_suggestion(rest)

        if sub == "help":
            if not rest:
                return formatter.format_list()
            return formatter.format_command(rest)

        if sub == "sanitize":
            if not rest:
                return "Usage: /input sanitize <text>"
            result = sanitizer.sanitize(rest)
            return json.dumps(
                {
                    "original": result.original,
                    "sanitized": result.sanitized,
                    "warnings": result.warnings,
                    "was_modified": result.was_modified,
                },
                indent=2,
            )

        return (
            "Usage: /input <sub>\n"
            "  parse <cmd> <args>    -- parse arguments\n"
            "  suggest <command>     -- did-you-mean suggestions\n"
            "  help [command]        -- command help\n"
            "  sanitize <text>       -- sanitize input"
        )

    registry.register(SlashCommand("input", "Input validation & user guidance (Q140)", input_handler))
