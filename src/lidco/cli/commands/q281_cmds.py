"""Q281 CLI commands: /fact-check, /validate-refs, /consistency, /grounding."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q281 slash commands."""

    async def fact_check_handler(args: str) -> str:
        from lidco.hallucination.checker import FactChecker

        checker = _state.setdefault("checker", FactChecker())
        if not args.strip():
            return "Usage: /fact-check <response text>"
        result = checker.check(args)
        return f"Claims: {len(result.claims)}, verified: {result.verified_count}, failed: {result.failed_count}, confidence: {result.overall_confidence}"

    async def validate_refs_handler(args: str) -> str:
        from lidco.hallucination.validator import ReferenceValidator

        validator = _state.setdefault("validator", ReferenceValidator())
        parts = args.strip().split(maxsplit=1)
        sub = parts[0] if parts else "summary"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "file":
            r = validator.validate_file(rest)
            return f"{rest}: {'valid' if r.valid else 'NOT FOUND'}"
        if sub == "function":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /validate-refs function <path> <name>"
            r = validator.validate_function(tokens[0], tokens[1])
            return f"{tokens[1]}: {'found' if r.valid else 'NOT FOUND'}"
        return json.dumps(validator.summary(), indent=2)

    async def consistency_handler(args: str) -> str:
        from lidco.hallucination.consistency import ConsistencyChecker

        checker = _state.setdefault("consistency", ConsistencyChecker())
        parts = args.strip().split(maxsplit=1)
        sub = parts[0] if parts else "summary"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "check":
            stmts = [s.strip() for s in rest.split("|") if s.strip()]
            result = checker.check(stmts)
            return f"Consistent: {result.is_consistent}, contradictions: {len(result.contradictions)}"
        if sub == "add-prior":
            checker.add_prior(rest)
            return "Prior statement added."
        return json.dumps(checker.summary(), indent=2)

    async def grounding_handler(args: str) -> str:
        from lidco.hallucination.grounding import GroundingEngine

        engine = _state.setdefault("grounding", GroundingEngine())
        parts = args.strip().split(maxsplit=1)
        sub = parts[0] if parts else "summary"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "add-source":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /grounding add-source <id> <content>"
            engine.add_source(tokens[0], tokens[1])
            return f"Source added: {tokens[0]}"
        if sub == "check":
            claims = [c.strip() for c in rest.split("|") if c.strip()]
            result = engine.ground(claims)
            return f"Grounded: {result.grounded_claims}/{result.total_claims}, traceability: {result.traceability_score}"
        return json.dumps(engine.summary(), indent=2)

    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("fact-check", "Verify factual claims", fact_check_handler))
    registry.register(SlashCommand("validate-refs", "Validate file/function references", validate_refs_handler))
    registry.register(SlashCommand("consistency", "Check response consistency", consistency_handler))
    registry.register(SlashCommand("grounding", "Ground responses in evidence", grounding_handler))
