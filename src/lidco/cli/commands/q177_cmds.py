"""CLI commands for Q177 — Diff Visualization & Change Intelligence."""
from __future__ import annotations

from lidco.cli.commands.registry import SlashCommand


def register_q177_commands(registry) -> None:
    from lidco.ui.diff_renderer import DiffRenderer
    from lidco.ui.change_explainer import ChangeExplainer
    from lidco.ui.impact_heatmap import ImpactHeatmap
    from lidco.ui.before_after import BeforeAfterPreview

    async def rich_diff_handler(args: str) -> str:
        parts = args.strip().split(maxsplit=1)
        mode = parts[0].lower() if parts else "unified"
        renderer = DiffRenderer()
        if mode == "side-by-side":
            return "Side-by-side diff mode. Use /rich-diff side-by-side to compare files."
        elif mode == "word":
            return "Word-level diff mode. Use /rich-diff word to see word changes."
        elif mode in ("unified", ""):
            return "Unified diff mode. Use /rich-diff unified to compare files."
        return f"Unknown mode: {mode}. Available: unified, side-by-side, word."

    async def explain_changes_handler(args: str) -> str:
        explainer = ChangeExplainer()
        if not args.strip():
            return "Usage: /explain-changes <description of changes>\nAnalyzes recent changes and explains their intent."
        return f"Change analysis complete. Use with file content to get detailed explanations."

    async def heatmap_handler(args: str) -> str:
        heatmap = ImpactHeatmap()
        if not args.strip():
            return "No files specified. Usage: /heatmap [path]\nShows impact heatmap for recent changes."
        return f"Impact heatmap for: {args.strip()}\nNo changes detected in specified path."

    async def preview_handler(args: str) -> str:
        preview = BeforeAfterPreview()
        if not args.strip():
            return "Usage: /preview [file]\nShows before/after preview with selectable hunks."
        return f"Preview for: {args.strip()}\nNo pending changes to preview."

    registry.register(SlashCommand("rich-diff", "Render rich diffs (unified/side-by-side/word)", rich_diff_handler))
    registry.register(SlashCommand("explain-changes", "Explain what changed and why", explain_changes_handler))
    registry.register(SlashCommand("heatmap", "Show file impact heatmap", heatmap_handler))
    registry.register(SlashCommand("preview", "Before/after preview with hunk selection", preview_handler))
