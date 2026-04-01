"""Q197 CLI commands: /suggest, /speculate, /prompt-history, /auto-complete."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q197 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    _state: dict[str, object] = {}

    # ------------------------------------------------------------------
    # /suggest
    # ------------------------------------------------------------------

    async def suggest_handler(args: str) -> str:
        from lidco.prompts.suggestion_engine import SuggestionEngine

        engine: SuggestionEngine | None = _state.get("suggestion_engine")  # type: ignore[assignment]
        if engine is None:
            engine = SuggestionEngine()
            _state["suggestion_engine"] = engine

        parts = args.strip().split(maxsplit=1)
        if parts and parts[0] == "add" and len(parts) > 1:
            engine = engine.add_history(parts[1])
            _state["suggestion_engine"] = engine
            return f"Added to history: {parts[1]}"

        n = 5
        if parts and parts[0].isdigit():
            n = int(parts[0])
        suggestions = engine.suggest(n=n)
        if not suggestions:
            return "No suggestions available."
        lines = [f"  [{s.confidence:.2f}] {s.text} ({s.source})" for s in suggestions]
        return "Suggestions:\n" + "\n".join(lines)

    # ------------------------------------------------------------------
    # /speculate
    # ------------------------------------------------------------------

    async def speculate_handler(args: str) -> str:
        from lidco.prompts.speculator import PromptSpeculator

        spec: PromptSpeculator | None = _state.get("speculator")  # type: ignore[assignment]
        if spec is None:
            spec = PromptSpeculator()
            _state["speculator"] = spec

        prompt = args.strip()
        if prompt:
            spec = spec.add_history(prompt)
            _state["speculator"] = spec

        result = spec.speculate()
        if not result.predicted_query:
            return "Not enough history to speculate."
        lines = [
            f"Predicted: {result.predicted_query}",
            f"Confidence: {result.confidence:.2f}",
            f"Prefetch: {', '.join(result.prefetch_keys) or 'none'}",
            f"Should prefetch: {spec.should_prefetch()}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /prompt-history
    # ------------------------------------------------------------------

    async def prompt_history_handler(args: str) -> str:
        from lidco.prompts.history_analyzer import HistoryAnalyzer

        analyzer: HistoryAnalyzer | None = _state.get("history_analyzer")  # type: ignore[assignment]
        if analyzer is None:
            analyzer = HistoryAnalyzer()
            _state["history_analyzer"] = analyzer

        if not analyzer.history:
            return "No prompt history recorded."

        patterns = analyzer.analyze()
        freq = analyzer.frequent_commands(n=5)

        lines = ["Prompt Patterns:"]
        for p in patterns:
            lines.append(f"  {p.category}: {p.frequency}x")
        lines.append("")
        lines.append("Top commands: " + ", ".join(freq))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /auto-complete
    # ------------------------------------------------------------------

    async def auto_complete_handler(args: str) -> str:
        from lidco.prompts.auto_complete import AutoComplete

        ac: AutoComplete | None = _state.get("auto_complete")  # type: ignore[assignment]
        if ac is None:
            ac = AutoComplete()
            _state["auto_complete"] = ac

        prefix = args.strip()
        if not prefix:
            return "Usage: /auto-complete <prefix>"

        completions = ac.complete(prefix)
        if not completions:
            return f"No completions for '{prefix}'."
        lines = [f"  [{c.score:.2f}] {c.text} ({c.kind})" for c in completions]
        return "Completions:\n" + "\n".join(lines)

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------

    registry.register(SlashCommand("suggest", "Get prompt suggestions", suggest_handler))
    registry.register(SlashCommand("speculate", "Predict next prompt", speculate_handler))
    registry.register(SlashCommand("prompt-history", "Analyze prompt history patterns", prompt_history_handler))
    registry.register(SlashCommand("auto-complete", "Auto-complete prompts", auto_complete_handler))
