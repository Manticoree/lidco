"""Q146 CLI commands: /edit undo/redo/preview/status."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q146 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def edit_handler(args: str) -> str:
        from lidco.editing.safe_editor import SafeEditor
        from lidco.editing.change_preview import ChangePreview
        from lidco.editing.undo_stack import UndoStack

        # Lazy init
        if "stack" not in _state:
            _state["stack"] = UndoStack()
        if "editor" not in _state:
            _state["editor"] = SafeEditor(undo_stack=_state["stack"])  # type: ignore[arg-type]
        if "preview" not in _state:
            _state["preview"] = ChangePreview()

        editor: SafeEditor = _state["editor"]  # type: ignore[assignment]
        preview_tool: ChangePreview = _state["preview"]  # type: ignore[assignment]
        stack: UndoStack = _state["stack"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "undo":
            result = editor.undo()
            if result is None:
                return "Nothing to undo."
            if result.success:
                return f"Undo successful: {result.transaction.label if result.transaction else 'unknown'}"
            return f"Undo failed: {result.error}"

        if sub == "redo":
            result = editor.redo()
            if result is None:
                return "Nothing to redo."
            if result.success:
                return f"Redo successful: {result.transaction.label if result.transaction else 'unknown'}"
            return f"Redo failed: {result.error}"

        if sub == "preview":
            info = editor.preview_next_undo()
            if info is None:
                return "Nothing to preview."
            return info

        if sub == "status":
            st = stack.state()
            lines = [
                f"Undo depth: {st.undo_depth}",
                f"Redo depth: {st.redo_depth}",
            ]
            if st.current_label:
                lines.append(f"Current: {st.current_label}")
            return "\n".join(lines)

        if sub == "diff":
            # diff <old> <new> — compare two strings (for demo/testing)
            diff_parts = rest.split("|", maxsplit=1)
            if len(diff_parts) < 2:
                return "Usage: /edit diff <old_text>|<new_text>"
            old_text = diff_parts[0]
            new_text = diff_parts[1]
            if not preview_tool.has_changes(old_text, new_text):
                return "No changes."
            lines = preview_tool.preview(old_text, new_text)
            return preview_tool.format_preview(lines)

        return (
            "Usage: /edit <sub>\n"
            "  undo                  -- undo last edit\n"
            "  redo                  -- redo last undo\n"
            "  preview               -- preview next undo\n"
            "  status                -- show undo/redo stack state\n"
            "  diff <old>|<new>      -- preview diff between texts"
        )

    registry.register(SlashCommand("edit", "Undo/redo & edit safety (Q146)", edit_handler))
