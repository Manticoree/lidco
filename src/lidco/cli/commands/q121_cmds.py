"""Q121 CLI commands: /patch."""
from __future__ import annotations

_state: dict = {}


def register(registry) -> None:
    """Register Q121 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def patch_handler(args: str) -> str:
        from lidco.editing.patch_parser import PatchParser
        from lidco.editing.patch_applier import PatchApplier
        from lidco.editing.edit_diff import EditDiff

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "parse":
            text = rest or _state.get("patch_text", "")
            if not text:
                return "Usage: /patch parse <unified-diff-text>"
            parser = PatchParser()
            files = parser.parse(text)
            _state["parsed_files"] = files
            return parser.summary(files)

        if sub == "apply":
            original = _state.get("original", "")
            files = _state.get("parsed_files")
            if not original:
                return "No original text in state. Set _state['original'] first."
            if not files:
                return "No parsed patch. Run /patch parse first."
            applier = PatchApplier()
            result = applier.apply(original, files[0])
            if result.success:
                _state["applied_text"] = result.result_text
                return f"Patch applied successfully. Result length: {len(result.result_text)} chars."
            return f"Apply failed: {result.error}"

        if sub == "diff":
            sub_parts = rest.split(maxsplit=1)
            if len(sub_parts) < 2:
                old = _state.get("original", "")
                new = _state.get("applied_text", "")
                if not old and not new:
                    return "Usage: /patch diff <old_text> <new_text> or set _state['original'/'applied_text']"
            else:
                old, new = sub_parts[0], sub_parts[1]
            differ = EditDiff()
            diff_text = differ.unified_diff(old, new, filename="file")
            return diff_text or "No differences."

        if sub == "stats":
            old = _state.get("original", "")
            new = _state.get("applied_text", "")
            if not old and not new:
                return "No texts in state. Run /patch apply first."
            differ = EditDiff()
            s = differ.stats(old, new)
            return f"Added: {s['added']}, Removed: {s['removed']}, Unchanged: {s['unchanged']}"

        return (
            "Usage: /patch <sub>\n"
            "  parse <diff>  -- parse unified diff, show summary\n"
            "  apply         -- apply parsed patch to _state['original']\n"
            "  diff          -- show diff between original and applied\n"
            "  stats         -- show diff statistics"
        )

    registry.register(SlashCommand("patch", "Patch parser and applier", patch_handler))
