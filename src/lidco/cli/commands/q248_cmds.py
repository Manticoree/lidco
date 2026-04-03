"""Q248 CLI commands: /turn-analysis, /patterns, /predict-success, /export-conversation."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q248 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /turn-analysis
    # ------------------------------------------------------------------

    async def turn_analysis_handler(args: str) -> str:
        from lidco.conversation.turn_analyzer import TurnAnalyzer

        msgs = _get_messages(registry)
        analyzer = TurnAnalyzer(msgs)
        sub = args.strip().lower()

        if sub == "summary":
            return analyzer.summary()

        if sub == "deltas":
            deltas = analyzer.token_deltas()
            if not deltas:
                return "No turns."
            return "Token deltas: " + ", ".join(str(d) for d in deltas)

        if sub.isdigit():
            idx = int(sub)
            try:
                ta = analyzer.analyze_turn(idx)
            except IndexError:
                return f"Turn {idx} out of range (0–{len(msgs) - 1})."
            return (
                f"Turn {ta.index} ({ta.role}): ~{ta.token_estimate} tokens, "
                f"tool_calls={ta.has_tool_calls}, files={ta.files_mentioned}, "
                f"score={ta.score}"
            )

        return (
            "Usage: /turn-analysis <subcommand>\n"
            "  summary        — overview of all turns\n"
            "  deltas         — token changes per turn\n"
            "  <index>        — analyze a specific turn"
        )

    # ------------------------------------------------------------------
    # /patterns
    # ------------------------------------------------------------------

    async def patterns_handler(args: str) -> str:
        from lidco.conversation.pattern_detector import PatternDetector

        msgs = _get_messages(registry)
        detector = PatternDetector(msgs)
        sub = args.strip().lower()

        if sub == "loops":
            loops = detector.detect_loops()
            if not loops:
                return "No loops detected."
            lines = [f"Found {len(loops)} loop(s):"]
            for lp in loops:
                lines.append(f"  indices={lp['indices']} preview={lp['content_preview']!r}")
            return "\n".join(lines)

        if sub == "dead-ends":
            de = detector.detect_dead_ends()
            if not de:
                return "No dead ends detected."
            return "Dead-end turns: " + ", ".join(str(i) for i in de)

        if sub == "retries":
            retries = detector.detect_excessive_retries()
            if not retries:
                return "No excessive retries detected."
            lines = [f"Found {len(retries)} retry pattern(s):"]
            for r in retries:
                lines.append(f"  tool={r['tool']} count={r['count']} start={r['start_index']}")
            return "\n".join(lines)

        if sub in ("all", "summary", ""):
            return detector.summary()

        return (
            "Usage: /patterns <subcommand>\n"
            "  loops      — detect repeated messages\n"
            "  dead-ends  — detect dead-end turns\n"
            "  retries    — detect excessive tool retries\n"
            "  all        — run all detectors"
        )

    # ------------------------------------------------------------------
    # /predict-success
    # ------------------------------------------------------------------

    async def predict_success_handler(args: str) -> str:
        from lidco.conversation.success_predictor import SuccessPredictor

        msgs = _get_messages(registry)
        predictor = SuccessPredictor(msgs)
        sub = args.strip().lower()

        if sub == "health":
            h = predictor.conversation_health()
            return (
                f"Length: {h['length']} | Error rate: {h['error_rate']} | "
                f"Diversity: {h['diversity']} | Score: {h['score']}"
            )

        pred = predictor.predict()
        factors = ", ".join(pred.factors) if pred.factors else "none"
        return (
            f"Likelihood: {pred.likelihood} | Factors: {factors} | "
            f"Recommendation: {pred.recommendation}"
        )

    # ------------------------------------------------------------------
    # /export-conversation
    # ------------------------------------------------------------------

    async def export_conversation_handler(args: str) -> str:
        from lidco.conversation.exporter import ConversationExporter

        msgs = _get_messages(registry)
        fmt = args.strip().lower() or "markdown"
        exporter = ConversationExporter(msgs)
        try:
            return exporter.export(fmt)
        except ValueError:
            return f"Unsupported format: {fmt}. Use markdown, json, or html."

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _get_messages(reg) -> list[dict]:
        """Extract messages from registry session, or return empty list."""
        session = getattr(reg, "_session", None)
        if session is None:
            return []
        return list(getattr(session, "messages", []))

    registry.register(SlashCommand("turn-analysis", "Analyze conversation turns", turn_analysis_handler))
    registry.register(SlashCommand("patterns", "Detect conversation anti-patterns", patterns_handler))
    registry.register(SlashCommand("predict-success", "Predict conversation success", predict_success_handler))
    registry.register(SlashCommand("export-conversation", "Export conversation to file", export_conversation_handler))
