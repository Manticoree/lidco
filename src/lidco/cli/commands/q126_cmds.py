"""Q126 CLI commands: /suggest."""
from __future__ import annotations

_state: dict = {}


def register(registry) -> None:
    """Register Q126 commands."""
    from lidco.cli.commands.registry import SlashCommand

    async def suggest_handler(args: str) -> str:
        from lidco.proactive.suggestion_engine import SuggestionEngine
        from lidco.proactive.smell_detector import SmellDetector
        from lidco.proactive.change_impact2 import ChangeImpactAnalyzer
        from lidco.proactive.auto_suggestion import AutoSuggestion

        if "engine" not in _state:
            _state["engine"] = SuggestionEngine.with_defaults()
        if "detector" not in _state:
            _state["detector"] = SmellDetector()
        if "impact" not in _state:
            _state["impact"] = ChangeImpactAnalyzer()
        if "auto" not in _state:
            _state["auto"] = AutoSuggestion(
                engine=_state["engine"], detector=_state["detector"]
            )

        engine: SuggestionEngine = _state["engine"]
        detector: SmellDetector = _state["detector"]
        impact_analyzer: ChangeImpactAnalyzer = _state["impact"]
        auto: AutoSuggestion = _state["auto"]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "analyze":
            if not rest:
                return "Usage: /suggest analyze <code>"
            suggestions = engine.analyze(rest)
            if not suggestions:
                return "No suggestions found."
            lines = [f"Suggestions ({len(suggestions)}):"]
            for s in suggestions[:15]:
                lines.append(f"  [{s.category}] {s.message} (conf={s.confidence:.2f})")
            return "\n".join(lines)

        if sub == "smells":
            if not rest:
                return "Usage: /suggest smells <code>"
            smells = detector.detect(rest)
            if not smells:
                return "No smells detected."
            lines = [f"Smells ({len(smells)}):"]
            for s in smells[:15]:
                lines.append(f"  [{s.kind}] [{s.severity}] {s.description}")
            return "\n".join(lines)

        if sub == "impact":
            if not rest:
                return "Usage: /suggest impact <module>"
            report = impact_analyzer.analyze(rest.strip())
            lines = [f"Impact of changing '{report.changed_file}':"]
            if report.directly_affected:
                lines.append(f"  Direct ({len(report.directly_affected)}): {', '.join(report.directly_affected)}")
            else:
                lines.append("  Direct: none")
            if report.transitively_affected:
                lines.append(f"  Transitive ({len(report.transitively_affected)}): {', '.join(report.transitively_affected)}")
            else:
                lines.append("  Transitive: none")
            lines.append(f"  Total affected: {report.total_affected}")
            return "\n".join(lines)

        if sub == "top":
            # top N suggestions from last analyze run
            if "last_suggestions" not in _state:
                return "No suggestions available. Run /suggest analyze first."
            try:
                n = int(rest.strip()) if rest.strip() else 5
            except ValueError:
                n = 5
            top = engine.top_n(_state["last_suggestions"], n)
            if not top:
                return "No suggestions."
            lines = [f"Top {len(top)} suggestions:"]
            for s in top:
                lines.append(f"  [{s.priority}] [{s.category}] {s.message}")
            return "\n".join(lines)

        return (
            "Usage: /suggest <sub>\n"
            "  analyze <code>   -- run suggestion rules on code\n"
            "  smells <code>    -- detect code smells\n"
            "  impact <module>  -- show change impact\n"
            "  top [n]          -- show top N suggestions from last analysis"
        )

    registry.register(SlashCommand("suggest", "Smart suggestions and smell detection", suggest_handler))
