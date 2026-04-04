"""Q275 CLI commands: /classify-error, /recovery, /self-heal, /error-patterns."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q275 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /classify-error <error_message>
    # ------------------------------------------------------------------

    async def classify_error_handler(args: str) -> str:
        from lidco.recovery.classifier import ErrorClassifier

        if "classifier" not in _state:
            _state["classifier"] = ErrorClassifier()
        clf: ErrorClassifier = _state["classifier"]  # type: ignore[assignment]

        msg = args.strip()
        if not msg:
            return "Usage: /classify-error <error_message>"

        result = clf.classify(msg)
        return json.dumps(
            {
                "type": result.type,
                "confidence": result.confidence,
                "indicators": result.indicators,
                "suggestion": result.suggestion,
            },
            indent=2,
        )

    registry.register(
        SlashCommand("classify-error", "Classify an error message", classify_error_handler)
    )

    # ------------------------------------------------------------------
    # /recovery [chain <type> | next <type> <attempt>]
    # ------------------------------------------------------------------

    async def recovery_handler(args: str) -> str:
        from lidco.recovery.strategy import RecoveryStrategy

        if "strategy" not in _state:
            _state["strategy"] = RecoveryStrategy()
        strat: RecoveryStrategy = _state["strategy"]  # type: ignore[assignment]

        parts = args.strip().split()
        sub = parts[0].lower() if parts else ""

        if sub == "chain":
            if len(parts) < 2:
                return "Usage: /recovery chain <error_type>"
            chain = strat.get_chain(parts[1])
            actions = [
                {"type": a.type, "description": a.description, "max_attempts": a.max_attempts}
                for a in chain.actions
            ]
            return json.dumps({"error_type": chain.error_type, "actions": actions}, indent=2)

        if sub == "next":
            if len(parts) < 3:
                return "Usage: /recovery next <error_type> <attempt>"
            try:
                attempt = int(parts[2])
            except ValueError:
                return "Attempt must be an integer."
            action = strat.next_action(parts[1], attempt)
            if action is None:
                return "No more actions — recovery exhausted."
            return json.dumps(
                {"type": action.type, "description": action.description, "backoff_seconds": action.backoff_seconds},
                indent=2,
            )

        # Default: summary
        return json.dumps(strat.summary(), indent=2)

    registry.register(
        SlashCommand("recovery", "Show recovery strategy", recovery_handler)
    )

    # ------------------------------------------------------------------
    # /self-heal <error_message> [code]
    # ------------------------------------------------------------------

    async def self_heal_handler(args: str) -> str:
        from lidco.recovery.self_heal import SelfHealEngine

        if "healer" not in _state:
            _state["healer"] = SelfHealEngine()
        healer: SelfHealEngine = _state["healer"]  # type: ignore[assignment]

        parts = args.strip().split("|", maxsplit=1)
        msg = parts[0].strip()
        code = parts[1].strip() if len(parts) > 1 else ""

        if not msg:
            return "Usage: /self-heal <error_message> [| code]"

        result = healer.heal(msg, code)
        if result is None:
            return "No auto-fix available for this error."
        return json.dumps(
            {
                "error_type": result.error_type,
                "fix_applied": result.fix_applied,
                "success": result.success,
                "fixed": result.fixed[:200],
            },
            indent=2,
        )

    registry.register(
        SlashCommand("self-heal", "Attempt auto-fix for an error", self_heal_handler)
    )

    # ------------------------------------------------------------------
    # /error-patterns [suggest <error> | record <pattern> <fix> <success> | top]
    # ------------------------------------------------------------------

    async def error_patterns_handler(args: str) -> str:
        from lidco.recovery.learner import ErrorPatternLearner

        if "learner" not in _state:
            _state["learner"] = ErrorPatternLearner()
        learner: ErrorPatternLearner = _state["learner"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "suggest":
            if not rest:
                return "Usage: /error-patterns suggest <error_message>"
            suggestions = learner.suggest(rest)
            if not suggestions:
                return "No matching resolutions found."
            items = [
                {"pattern": s.error_pattern, "fix": s.fix_description, "success_count": s.success_count}
                for s in suggestions
            ]
            return json.dumps(items, indent=2)

        if sub == "record":
            tokens = rest.split("|")
            if len(tokens) < 3:
                return "Usage: /error-patterns record <pattern> | <fix> | <true/false>"
            pattern = tokens[0].strip()
            fix = tokens[1].strip()
            success = tokens[2].strip().lower() in ("true", "1", "yes")
            res = learner.record_resolution(pattern, fix, success)
            return f"Recorded: {res.error_pattern} — {res.fix_description} (success={success})"

        if sub == "top":
            top = learner.top_fixes()
            if not top:
                return "No resolutions recorded."
            items = [
                {"pattern": r.error_pattern, "fix": r.fix_description, "success_count": r.success_count}
                for r in top
            ]
            return json.dumps(items, indent=2)

        # Default: summary
        return json.dumps(learner.summary(), indent=2)

    registry.register(
        SlashCommand("error-patterns", "Error pattern learner", error_patterns_handler)
    )
