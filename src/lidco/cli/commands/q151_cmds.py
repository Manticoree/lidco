"""Q151 CLI commands: /merge."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q151 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def merge_handler(args: str) -> str:
        from lidco.merge.three_way import ThreeWayMerge
        from lidco.merge.conflict_resolver import ConflictResolver
        from lidco.merge.diff_stats import DiffStatsCollector
        from lidco.merge.patch_generator import PatchGenerator

        if "merger" not in _state:
            _state["merger"] = ThreeWayMerge()
        if "resolver" not in _state:
            _state["resolver"] = ConflictResolver()
        if "stats" not in _state:
            _state["stats"] = DiffStatsCollector()
        if "patcher" not in _state:
            _state["patcher"] = PatchGenerator()

        merger: ThreeWayMerge = _state["merger"]  # type: ignore[assignment]
        resolver: ConflictResolver = _state["resolver"]  # type: ignore[assignment]
        stats_collector: DiffStatsCollector = _state["stats"]  # type: ignore[assignment]
        patcher: PatchGenerator = _state["patcher"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "three-way":
            return _handle_three_way(merger, rest)

        if sub == "resolve":
            return _handle_resolve(merger, resolver, rest)

        if sub == "stats":
            return _handle_stats(stats_collector, rest)

        if sub == "patch":
            return _handle_patch(patcher, rest)

        return (
            "Usage: /merge <subcommand>\n"
            "Subcommands: three-way, resolve, stats, patch"
        )

    registry.register(
        SlashCommand("merge", "Diff & merge tools", merge_handler)
    )


def _handle_three_way(merger, rest: str) -> str:
    """Handle /merge three-way <json>."""
    if not rest.strip():
        return (
            'Usage: /merge three-way <json>\n'
            'JSON: {"base": "...", "ours": "...", "theirs": "..."}'
        )
    try:
        data = json.loads(rest)
    except json.JSONDecodeError as exc:
        return f"Invalid JSON: {exc}"

    base = data.get("base", "")
    ours = data.get("ours", "")
    theirs = data.get("theirs", "")

    result = merger.merge(base, ours, theirs)

    if result.has_conflicts:
        formatted = merger.format_conflicts(result)
        return (
            f"Merge has {len(result.conflicts)} conflict(s), "
            f"{result.auto_resolved} auto-resolved.\n{formatted}"
        )
    return f"Clean merge ({result.auto_resolved} auto-resolved):\n{result.merged}"


def _handle_resolve(merger, resolver, rest: str) -> str:
    """Handle /merge resolve <json>."""
    if not rest.strip():
        return (
            'Usage: /merge resolve <json>\n'
            'JSON: {"base": "...", "ours": "...", "theirs": "...", '
            '"strategy": "ours|theirs|both"}'
        )
    try:
        data = json.loads(rest)
    except json.JSONDecodeError as exc:
        return f"Invalid JSON: {exc}"

    base = data.get("base", "")
    ours = data.get("ours", "")
    theirs = data.get("theirs", "")
    strategy = data.get("strategy", "ours")

    result = merger.merge(base, ours, theirs)
    if not result.has_conflicts:
        return f"No conflicts to resolve.\n{result.merged}"

    resolutions = []
    for idx, conflict in enumerate(result.conflicts):
        if strategy == "theirs":
            r = resolver.resolve_theirs(conflict)
        elif strategy == "both":
            r = resolver.resolve_both(conflict)
        else:
            r = resolver.resolve_ours(conflict)
        r.conflict_index = idx
        resolutions.append(r)

    final = resolver.apply_resolutions(result, resolutions)
    return f"Resolved {len(resolutions)} conflict(s) with '{strategy}':\n{final}"


def _handle_stats(stats_collector, rest: str) -> str:
    """Handle /merge stats <json>."""
    if not rest.strip():
        return (
            'Usage: /merge stats <json>\n'
            'JSON: {"old": "...", "new": "...", "path": "file.py"}'
        )
    try:
        data = json.loads(rest)
    except json.JSONDecodeError as exc:
        return f"Invalid JSON: {exc}"

    old = data.get("old", "")
    new = data.get("new", "")
    path = data.get("path", "")

    stat = stats_collector.compute(old, new, path)
    return stats_collector.format_stat_line(stat)


def _handle_patch(patcher, rest: str) -> str:
    """Handle /merge patch <json>."""
    if not rest.strip():
        return (
            'Usage: /merge patch <json>\n'
            'JSON: {"path": "file.py", "old": "...", "new": "..."}'
        )
    try:
        data = json.loads(rest)
    except json.JSONDecodeError as exc:
        return f"Invalid JSON: {exc}"

    path = data.get("path", "")
    old = data.get("old", "")
    new = data.get("new", "")

    patch = patcher.generate(path, old, new)
    if not patch:
        return "No differences found."
    return patch
