"""Q134 CLI commands: /transform (rename | extract | inline | dead-code)."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q134 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def transform_handler(args: str) -> str:
        from lidco.transform.variable_renamer import VariableRenamer
        from lidco.transform.method_extractor import MethodExtractor
        from lidco.transform.inline_expander import InlineExpander
        from lidco.transform.dead_code import DeadCodeEliminator

        if "renamer" not in _state:
            _state["renamer"] = VariableRenamer()
        if "extractor" not in _state:
            _state["extractor"] = MethodExtractor()
        if "inliner" not in _state:
            _state["inliner"] = InlineExpander()
        if "eliminator" not in _state:
            _state["eliminator"] = DeadCodeEliminator()

        renamer: VariableRenamer = _state["renamer"]  # type: ignore[assignment]
        extractor: MethodExtractor = _state["extractor"]  # type: ignore[assignment]
        inliner: InlineExpander = _state["inliner"]  # type: ignore[assignment]
        eliminator: DeadCodeEliminator = _state["eliminator"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "rename":
            sub_parts = rest.split(maxsplit=2)
            if len(sub_parts) < 3:
                return "Usage: /transform rename <old_name> <new_name> <source>"
            old_name, new_name, source = sub_parts[0], sub_parts[1], sub_parts[2]
            if not renamer.is_safe_rename(source, old_name, new_name):
                return f"Rename '{old_name}' -> '{new_name}' is not safe."
            result = renamer.rename(source, old_name, new_name)
            return json.dumps({
                "old_name": result.old_name,
                "new_name": result.new_name,
                "occurrences": result.occurrences,
                "source": result.source,
            }, indent=2)

        if sub == "extract":
            sub_parts = rest.split(maxsplit=3)
            if len(sub_parts) < 4:
                return "Usage: /transform extract <start_line> <end_line> <method_name> <source>"
            try:
                start_line = int(sub_parts[0])
                end_line = int(sub_parts[1])
            except ValueError:
                return "start_line and end_line must be integers."
            method_name = sub_parts[2]
            source = sub_parts[3] if len(sub_parts) > 3 else ""
            result = extractor.extract(source, start_line, end_line, method_name)
            return json.dumps({
                "method_name": result.method_name,
                "parameters": result.parameters,
                "body": result.body,
            }, indent=2)

        if sub == "inline":
            sub_parts = rest.split(maxsplit=1)
            if len(sub_parts) < 2:
                return "Usage: /transform inline <variable_name> <source>"
            var_name, source = sub_parts[0], sub_parts[1]
            if not inliner.can_inline(source, var_name):
                return f"Cannot inline '{var_name}' — multiple assignments or side effects."
            result = inliner.inline_variable(source, var_name)
            return json.dumps({
                "variable_name": result.variable_name,
                "value_expr": result.value_expr,
                "replacements": result.replacements,
            }, indent=2)

        if sub == "dead-code":
            if not rest.strip():
                return "Usage: /transform dead-code <source>"
            result = eliminator.eliminate(rest)
            return json.dumps({
                "removed_names": result.removed_names,
                "removed_lines": result.removed_lines,
            }, indent=2)

        return (
            "Usage: /transform <sub>\n"
            "  rename <old> <new> <source>               -- rename variable/param\n"
            "  extract <start> <end> <name> <source>     -- extract method\n"
            "  inline <var> <source>                      -- inline variable\n"
            "  dead-code <source>                         -- eliminate dead code"
        )

    registry.register(SlashCommand("transform", "AST code transformations (Q134)", transform_handler))
