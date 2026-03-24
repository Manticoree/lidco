"""Slash commands for Arena mode and leaderboard."""
from __future__ import annotations

from typing import Any

_last_arena_result: Any = None
_leaderboard: Any = None


def _get_leaderboard() -> Any:
    global _leaderboard
    if _leaderboard is None:
        try:
            from lidco.agents.arena_leaderboard import ArenaLeaderboard
            _leaderboard = ArenaLeaderboard()
        except Exception:
            _leaderboard = None
    return _leaderboard


# ------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------

async def arena_compare_handler(args: str = "") -> str:
    """/arena compare <model_a> <model_b> <task> — run arena comparison."""
    global _last_arena_result
    parts = args.strip().split(None, 2)
    if len(parts) < 3:
        return "Usage: /arena compare <model_a> <model_b> <task>"
    model_a, model_b, task = parts[0], parts[1], parts[2]
    try:
        from lidco.agents.arena import ArenaMode
        arena = ArenaMode(models=[model_a, model_b])
        result = arena.run(task)
        _last_arena_result = (arena, result)
        return arena.format_comparison(result)
    except Exception as exc:
        return f"Arena compare failed: {exc}"


async def arena_leaderboard_handler(args: str = "") -> str:
    """/arena leaderboard — show model win rates."""
    lb = _get_leaderboard()
    if lb is None:
        return "Leaderboard unavailable."
    board = lb.leaderboard()
    if not board:
        return "No votes recorded yet. Run /arena compare to start."
    lines = ["Arena Leaderboard:", "| Model | Wins | Appearances | Win Rate |",
             "|-------|------|-------------|----------|"]
    for s in board:
        lines.append(f"| {s.model} | {s.wins} | {s.appearances} | {s.win_rate:.1%} |")
    return "\n".join(lines)


async def arena_vote_handler(args: str = "") -> str:
    """/arena vote <model> — record vote for last arena comparison."""
    global _last_arena_result
    model = args.strip()
    if not model:
        return "Usage: /arena vote <model>"
    if _last_arena_result is None:
        return "No arena comparison active. Run /arena compare first."
    lb = _get_leaderboard()
    if lb is None:
        return "Leaderboard unavailable."
    arena, result = _last_arena_result
    models = [e.model for e in result.entries]
    if model not in models:
        return f"Model '{model}' not in last comparison. Options: {', '.join(models)}"
    try:
        import hashlib, time
        from lidco.agents.arena_leaderboard import VoteRecord
        ph = hashlib.md5(result.task.encode()).hexdigest()[:8]
        vote = VoteRecord(
            model_a=models[0], model_b=models[1] if len(models) > 1 else models[0],
            winner=model, task_type="general", prompt_hash=ph, timestamp=time.time()
        )
        lb.record_vote(vote)
        return f"Vote recorded: {model} wins."
    except Exception as exc:
        return f"Failed to record vote: {exc}"


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register_arena_commands(registry: Any) -> None:
    from lidco.cli.commands.registry import SlashCommand
    registry.register(SlashCommand("arena compare", "Compare two models on a task", arena_compare_handler))
    registry.register(SlashCommand("arena leaderboard", "Show model win rates", arena_leaderboard_handler))
    registry.register(SlashCommand("arena vote", "Record vote for last comparison", arena_vote_handler))
