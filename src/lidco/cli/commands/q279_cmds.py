"""Q279 CLI commands: /debate, /personas, /evaluate-args, /consensus."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q279 slash commands."""

    async def debate_handler(args: str) -> str:
        from lidco.debate.orchestrator import DebateOrchestrator, DebateConfig, DebateRole

        parts = args.strip().split(maxsplit=1)
        sub = parts[0] if parts else "status"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "start":
            if not rest:
                return "Usage: /debate start <topic>"
            config = DebateConfig(topic=rest, rounds=3)
            orch = DebateOrchestrator(config)
            _state["debate"] = orch
            return f"Debate created: {rest}"
        if sub == "add":
            orch = _state.get("debate")
            if not orch:
                return "No active debate. Use /debate start <topic>"
            pair = rest.split(maxsplit=1)
            if len(pair) < 2:
                return "Usage: /debate add <agent_id> <role>"
            role_map = {"proposition": DebateRole.PROPOSITION, "opposition": DebateRole.OPPOSITION, "judge": DebateRole.JUDGE}
            role = role_map.get(pair[1].lower())
            if not role:
                return f"Unknown role: {pair[1]}"
            orch.add_participant(pair[0], role)
            return f"Added {pair[0]} as {pair[1]}"
        if sub == "status":
            orch = _state.get("debate")
            if not orch:
                return "No active debate."
            return json.dumps(orch.summary(), indent=2)
        return f"Unknown sub-command: {sub}"

    async def personas_handler(args: str) -> str:
        from lidco.debate.personas import PersonaRegistry

        reg = _state.setdefault("persona_reg", PersonaRegistry())
        sub = args.strip().split(maxsplit=1)[0] if args.strip() else "list"

        if sub == "list":
            return ", ".join(reg.names())
        if sub == "show":
            name = args.strip().split(maxsplit=1)[1] if len(args.strip().split()) > 1 else ""
            p = reg.get(name)
            if not p:
                return f"Unknown persona: {name}"
            return f"{p.name}: {p.description}\nTraits: {', '.join(p.traits)}"
        return f"Unknown sub-command: {sub}"

    async def evaluate_args_handler(args: str) -> str:
        from lidco.debate.evaluator import ArgumentEvaluator

        evaluator = _state.setdefault("evaluator", ArgumentEvaluator())
        if not args.strip():
            lb = evaluator.leaderboard()
            if not lb:
                return "No evaluations yet."
            return "\n".join(f"{a}: {s}" for a, s in lb)
        parts = args.strip().split("|", maxsplit=1)
        agent_id = parts[0].strip()
        content = parts[1].strip() if len(parts) > 1 else ""
        score = evaluator.evaluate(agent_id, content)
        return f"Score for {agent_id}: overall={score.overall} ({score.feedback or 'OK'})"

    async def consensus_handler(args: str) -> str:
        from lidco.debate.consensus import ConsensusBuilder

        builder = _state.setdefault("consensus", ConsensusBuilder())
        sub = args.strip().split(maxsplit=1)[0] if args.strip() else "status"
        rest = args.strip().split(maxsplit=1)[1] if len(args.strip().split()) > 1 else ""

        if sub == "vote":
            pair = rest.split(maxsplit=1)
            if len(pair) < 2:
                return "Usage: /consensus vote <agent_id> <position>"
            builder.cast_vote(pair[0], pair[1])
            return f"Vote recorded: {pair[0]} -> {pair[1]}"
        if sub == "build":
            result = builder.build(rest or "")
            return f"Decision: {result.decision} (confidence={result.confidence}, majority={result.majority_pct}%)"
        if sub == "status":
            return json.dumps(builder.summary(), indent=2)
        return f"Unknown sub-command: {sub}"

    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("debate", "Multi-agent debate orchestration", debate_handler))
    registry.register(SlashCommand("personas", "Manage debate personas", personas_handler))
    registry.register(SlashCommand("evaluate-args", "Evaluate debate arguments", evaluate_args_handler))
    registry.register(SlashCommand("consensus", "Build consensus from debate", consensus_handler))
