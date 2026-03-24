"""CLI commands for code navigation and explanation (Q86)."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.cli.commands.registry import CommandRegistry


def register_nav_commands(registry: "CommandRegistry") -> None:
    """Register /navigate, /explain, /refactor-suggest, /fix-error commands."""

    async def navigate_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        parts = args.strip().split(None, 1)
        if not parts:
            return "Usage: /navigate <symbol> [--callers]"
        symbol = parts[0]
        callers_only = len(parts) > 1 and "--callers" in parts[1]
        try:
            from lidco.navigation.code_navigator import CodeNavigator
            nav = CodeNavigator(".")
            if callers_only:
                locs = nav.callers(symbol)
                if not locs:
                    return f"No callers found for '{symbol}'"
                lines = [f"Callers of '{symbol}': {len(locs)}"]
                for loc in locs[:10]:
                    lines.append(f"  {loc.file}:{loc.line}  {loc.context.strip()[:60]}")
                return "\n".join(lines)
            result = nav.find(symbol)
            return result.format_summary()
        except Exception as e:
            return f"/navigate failed: {e}"

    async def explain_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        parts = args.strip().split(None, 1)
        if not parts:
            return "Usage: /explain <file_path> [function_name]"
        file_path = parts[0]
        func_name = parts[1].strip() if len(parts) > 1 else None
        try:
            from lidco.analysis.code_explainer import CodeExplainer
            from pathlib import Path
            explainer = CodeExplainer()
            if func_name:
                source = Path(file_path).read_text(encoding="utf-8", errors="replace") if Path(file_path).exists() else file_path
                explanation = explainer.explain_function(source, func_name)
            else:
                explanation = explainer.explain_file(file_path)
            return explanation.format()
        except Exception as e:
            return f"/explain failed: {e}"

    async def refactor_suggest_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        file_path = args.strip()
        if not file_path:
            return "Usage: /refactor-suggest <file_path>"
        try:
            from lidco.refactor.refactor_suggestor import RefactorSuggestor
            suggestor = RefactorSuggestor()
            report = suggestor.analyse_file(file_path)
            return report.format_summary()
        except Exception as e:
            return f"/refactor-suggest failed: {e}"

    async def fix_error_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        traceback_text = args.strip()
        if not traceback_text:
            return "Usage: /fix-error <traceback text>"
        try:
            from lidco.analysis.error_explainer import ErrorExplainer
            explainer = ErrorExplainer()
            return explainer.explain_text(traceback_text)
        except Exception as e:
            return f"/fix-error failed: {e}"

    from lidco.cli.commands.registry import SlashCommand
    registry.register(SlashCommand("navigate", "Find symbol definitions and references", navigate_handler))
    # Registered as /code-explain to avoid overriding tools_cmds.py's LLM-based /explain
    registry.register(SlashCommand("code-explain", "Explain a Python file or function (AST-based)", explain_handler))
    registry.register(SlashCommand("refactor-suggest", "Suggest structural refactoring improvements", refactor_suggest_handler))
    registry.register(SlashCommand("fix-error", "Explain a Python traceback and suggest fixes", fix_error_handler))
