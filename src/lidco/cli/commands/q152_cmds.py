"""Q152 CLI commands: /error."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q152 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def error_handler(args: str) -> str:
        from lidco.errors.categorizer import ErrorCategorizer
        from lidco.errors.friendly_messages import FriendlyMessages
        from lidco.errors.solution_suggester import SolutionSuggester
        from lidco.errors.report_formatter import ErrorReportFormatter

        # Lazy init
        if "categorizer" not in _state:
            _state["categorizer"] = ErrorCategorizer.with_defaults()
        if "translator" not in _state:
            _state["translator"] = FriendlyMessages.with_defaults()
        if "suggester" not in _state:
            _state["suggester"] = SolutionSuggester.with_defaults()
        if "formatter" not in _state:
            _state["formatter"] = ErrorReportFormatter(
                categorizer=_state["categorizer"],  # type: ignore[arg-type]
                translator=_state["translator"],  # type: ignore[arg-type]
                suggester=_state["suggester"],  # type: ignore[arg-type]
            )

        categorizer: ErrorCategorizer = _state["categorizer"]  # type: ignore[assignment]
        translator: FriendlyMessages = _state["translator"]  # type: ignore[assignment]
        suggester: SolutionSuggester = _state["suggester"]  # type: ignore[assignment]
        formatter: ErrorReportFormatter = _state["formatter"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "report":
            if not rest:
                return "Usage: /error report <error_message>"
            error = RuntimeError(rest)
            report = formatter.create_report(error)
            return formatter.format_detailed(report)

        if sub == "categorize":
            if not rest:
                return "Usage: /error categorize <error_message>"
            error = RuntimeError(rest)
            ce = categorizer.categorize(error)
            if ce.category:
                return f"Category: {ce.category.name} ({ce.category.severity})\nDescription: {ce.category.description}"
            return "No matching category found."

        if sub == "suggest":
            if not rest:
                return "Usage: /error suggest <error_message>"
            error = RuntimeError(rest)
            solutions = suggester.suggest(error)
            if not solutions:
                return "No solutions found."
            return suggester.format_solutions(solutions)

        if sub == "friendly":
            if not rest:
                return "Usage: /error friendly <error_message>"
            error = RuntimeError(rest)
            fe = translator.translate(error)
            return translator.format(fe)

        return "Usage: /error <report|categorize|suggest|friendly> <error_message>"

    registry.register(
        SlashCommand("error", "Error reporting & user-friendly messages", error_handler)
    )
