"""CLI commands for Q174 — Parallel Exploration."""
from __future__ import annotations

from lidco.cli.commands.registry import SlashCommand


def register_q174_commands(registry) -> None:  # type: ignore[no-untyped-def]
    from lidco.explore.spawner import ExplorationSpawner
    from lidco.explore.diff_presenter import DiffPresenter

    spawner = ExplorationSpawner()
    presenter = DiffPresenter()

    async def explore_handler(args: str) -> str:
        parts = args.strip().split()
        if not parts:
            return "Usage: /explore <prompt> [--variants N]\n\nSpawn parallel exploration variants."

        num_variants = 3
        prompt_parts: list[str] = []
        i = 0
        while i < len(parts):
            if parts[i] == "--variants" and i + 1 < len(parts):
                try:
                    num_variants = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                prompt_parts.append(parts[i])
                i += 1

        prompt = " ".join(prompt_parts)
        if not prompt:
            return "Error: No prompt provided."

        exp = spawner.create_exploration(prompt, num_variants)
        lines = [f"Exploration {exp.id} created with {len(exp.variants)} variants:"]
        for v in exp.variants:
            lines.append(f"  - {v.id} ({v.strategy}): {v.status}")
        return "\n".join(lines)

    async def explore_status_handler(args: str) -> str:
        explorations = spawner.list_explorations()
        if not explorations:
            return "No active explorations."
        lines = ["Explorations:"]
        for exp in explorations:
            completed = sum(1 for v in exp.variants if v.status == "completed")
            lines.append(f"  {exp.id}: {exp.status} ({completed}/{len(exp.variants)} variants done)")
        return "\n".join(lines)

    async def explore_pick_handler(args: str) -> str:
        variant_id = args.strip()
        if not variant_id:
            return "Usage: /explore-pick <variant_id>\n\nManually select a winning variant."
        return f"Selected variant: {variant_id}\nUse /explore-diff to compare before applying."

    async def explore_diff_handler(args: str) -> str:
        parts = args.strip().split()
        if len(parts) < 2:
            return "Usage: /explore-diff <id1> <id2>\n\nCompare two exploration variants."
        return presenter.format_diff_comparison("", "", label_a=parts[0], label_b=parts[1])

    registry.register(SlashCommand("explore", "Spawn parallel exploration variants", explore_handler))
    registry.register(SlashCommand("explore-status", "Check exploration status", explore_status_handler))
    registry.register(SlashCommand("explore-pick", "Select winning variant", explore_pick_handler))
    registry.register(SlashCommand("explore-diff", "Compare exploration variants", explore_diff_handler))
