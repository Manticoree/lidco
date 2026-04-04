"""Q280 CLI commands: /reflect, /confidence, /knowledge-boundary, /learning-journal."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q280 slash commands."""

    async def reflect_handler(args: str) -> str:
        from lidco.metacog.reflection import ReflectionEngine

        engine = _state.setdefault("reflection", ReflectionEngine())
        parts = args.strip().split(maxsplit=1)
        sub = parts[0] if parts else "summary"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "on":
            ref = engine.reflect(f"r-{len(engine.history())+1}", rest or "response text", task_type="general")
            return f"Quality: {ref.quality_score}, Confidence: {ref.confidence}"
        if sub == "history":
            h = engine.history()
            return f"{len(h)} reflections, avg quality: {engine.average_quality()}"
        if sub == "improvements":
            imps = engine.improvement_summary()
            return "\n".join(imps) if imps else "No improvements noted."
        return f"Avg quality: {engine.average_quality()}, total: {len(engine.history())}"

    async def confidence_handler(args: str) -> str:
        from lidco.metacog.calibrator import ConfidenceCalibrator

        cal = _state.setdefault("calibrator", ConfidenceCalibrator())
        parts = args.strip().split(maxsplit=1)
        sub = parts[0] if parts else "summary"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "predict":
            pair = rest.split(maxsplit=1)
            if len(pair) < 2:
                return "Usage: /confidence predict <id> <value> [confidence]"
            tokens = pair[1].split()
            predicted = tokens[0]
            conf = float(tokens[1]) if len(tokens) > 1 else 0.5
            cal.record_prediction(pair[0], predicted, conf)
            return f"Prediction recorded: {pair[0]}"
        if sub == "resolve":
            pair = rest.split(maxsplit=1)
            if len(pair) < 2:
                return "Usage: /confidence resolve <id> <actual>"
            result = cal.record_outcome(pair[0], pair[1])
            if not result:
                return f"Prediction {pair[0]} not found"
            return f"Resolved: correct={result.correct}"
        return json.dumps(cal.summary(), indent=2)

    async def boundary_handler(args: str) -> str:
        from lidco.metacog.boundary import KnowledgeBoundary

        kb = _state.setdefault("boundary", KnowledgeBoundary())
        parts = args.strip().split(maxsplit=1)
        sub = parts[0] if parts else "summary"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "assess":
            a = kb.assess(rest)
            return f"Category: {a.category}, confidence: {a.confidence}, within: {a.within_boundary}"
        if sub == "add-domain":
            kb.add_known_domain(rest)
            return f"Added domain: {rest}"
        return json.dumps(kb.summary(), indent=2)

    async def journal_handler(args: str) -> str:
        from lidco.metacog.journal import LearningJournal

        journal = _state.setdefault("journal", LearningJournal())
        parts = args.strip().split(maxsplit=1)
        sub = parts[0] if parts else "summary"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "log":
            entry = journal.log("current", rest or "lesson learned")
            return f"Logged: {entry.entry_id}"
        if sub == "search":
            results = journal.search(rest)
            return f"Found {len(results)} entries"
        if sub == "patterns":
            patterns = journal.extract_patterns()
            return "\n".join(f"{p['word']}: {p['frequency']}" for p in patterns) if patterns else "No patterns yet."
        return json.dumps(journal.summary(), indent=2)

    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("reflect", "Self-reflection on responses", reflect_handler))
    registry.register(SlashCommand("confidence", "Confidence calibration", confidence_handler))
    registry.register(SlashCommand("knowledge-boundary", "Knowledge boundary detection", boundary_handler))
    registry.register(SlashCommand("learning-journal", "Learning journal", journal_handler))
