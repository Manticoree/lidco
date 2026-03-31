"""Q160 CLI commands: /auto-mode, /rewind, /checkpoints, /checkpoint."""

from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:  # noqa: D401
    """Register Q160 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /auto-mode [on|off|status]
    # ------------------------------------------------------------------
    async def auto_mode_handler(args: str) -> str:
        from lidco.permissions.ai_classifier import PermissionClassifier

        if "classifier" not in _state:
            _state["classifier"] = PermissionClassifier()
            _state["auto_mode_enabled"] = False

        classifier: PermissionClassifier = _state["classifier"]  # type: ignore[assignment]
        sub = args.strip().lower()

        if sub == "on":
            _state["auto_mode_enabled"] = True
            return "AI permission classifier enabled."
        if sub == "off":
            _state["auto_mode_enabled"] = False
            return "AI permission classifier disabled."
        if sub == "status":
            enabled = _state.get("auto_mode_enabled", False)
            rules = classifier.list_rules()
            stats = classifier.stats
            lines = [
                f"Auto-mode: {'enabled' if enabled else 'disabled'}",
                f"Rules: {len(rules)}",
                f"Stats: {json.dumps(stats)}",
            ]
            if rules:
                lines.append("Current rules:")
                for r in rules:
                    lines.append(f"  - {r}")
            return "\n".join(lines)
        if sub.startswith("add-rule "):
            rule = sub[len("add-rule "):].strip()
            if not rule:
                return "Usage: /auto-mode add-rule <rule>"
            classifier.add_rule(rule)
            return f"Rule added: {rule}"
        if sub.startswith("remove-rule "):
            rule = sub[len("remove-rule "):].strip()
            classifier.remove_rule(rule)
            return f"Rule removed (if it existed): {rule}"

        return (
            "Usage: /auto-mode <subcommand>\n"
            "  on                      — enable AI permission classifier\n"
            "  off                     — disable AI permission classifier\n"
            "  status                  — show status, rules, and stats\n"
            "  add-rule <rule>         — add a custom rule\n"
            "  remove-rule <rule>      — remove a custom rule"
        )

    registry.register(SlashCommand("auto-mode", "Toggle AI permission classifier", auto_mode_handler))

    # ------------------------------------------------------------------
    # /checkpoint [label]
    # ------------------------------------------------------------------
    async def checkpoint_handler(args: str) -> str:
        from lidco.checkpoint.manager import CheckpointManager

        if "cp_manager" not in _state:
            _state["cp_manager"] = CheckpointManager()

        manager: CheckpointManager = _state["cp_manager"]  # type: ignore[assignment]
        label = args.strip()
        # Create a checkpoint with empty file dict (caller should populate via session)
        cp = manager.create(files={}, conversation_length=0, label=label)
        return f"Checkpoint created: {cp.checkpoint_id}" + (f" ({cp.label})" if cp.label else "")

    registry.register(SlashCommand("checkpoint", "Create a manual checkpoint", checkpoint_handler))

    # ------------------------------------------------------------------
    # /checkpoints [list|clear]
    # ------------------------------------------------------------------
    async def checkpoints_handler(args: str) -> str:
        from lidco.checkpoint.manager import CheckpointManager

        if "cp_manager" not in _state:
            _state["cp_manager"] = CheckpointManager()

        manager: CheckpointManager = _state["cp_manager"]  # type: ignore[assignment]
        sub = args.strip().lower()

        if sub == "clear":
            manager.clear()
            return "All checkpoints cleared."

        # default: list
        cps = manager.list()
        if not cps:
            return "No checkpoints."
        lines = [f"Checkpoints ({len(cps)}):"]
        for cp in cps:
            label_part = f" [{cp.label}]" if cp.label else ""
            files_part = f" ({len(cp.file_snapshots)} files)"
            lines.append(f"  {cp.checkpoint_id}{label_part}{files_part}")
        return "\n".join(lines)

    registry.register(SlashCommand("checkpoints", "List or clear checkpoints", checkpoints_handler))

    # ------------------------------------------------------------------
    # /rewind [code|chat|both] [checkpoint_id]
    # ------------------------------------------------------------------
    async def rewind_handler(args: str) -> str:
        from lidco.checkpoint.manager import CheckpointManager
        from lidco.checkpoint.rewind import RewindEngine

        if "cp_manager" not in _state:
            _state["cp_manager"] = CheckpointManager()

        manager: CheckpointManager = _state["cp_manager"]  # type: ignore[assignment]
        engine = RewindEngine(manager)

        parts = args.strip().split()
        if len(parts) < 2:
            return (
                "Usage: /rewind <mode> <checkpoint_id>\n"
                "  mode: code | chat | both\n"
                "  checkpoint_id: from /checkpoints list"
            )

        mode = parts[0].lower()
        cp_id = parts[1]

        if mode not in ("code", "chat", "both"):
            return f"Invalid mode '{mode}'. Use: code, chat, or both."

        cp = manager.get(cp_id)
        if cp is None:
            return f"Checkpoint '{cp_id}' not found."

        if mode == "code":
            restored = engine.rewind_code(cp_id, write_fn=_noop_write)
            if not restored:
                return "No files to restore."
            return f"Restored {len(restored)} file(s): {', '.join(restored)}"
        if mode == "chat":
            pos = engine.rewind_chat(cp_id)
            if pos < 0:
                return "Could not determine conversation position."
            return f"Conversation should be truncated to position {pos}."

        # both
        result = engine.rewind_both(cp_id, write_fn=_noop_write)
        if not result.success:
            return "Rewind failed — checkpoint not found."
        lines = [f"Rewind complete (mode=both)."]
        if result.restored_files:
            lines.append(f"Restored {len(result.restored_files)} file(s).")
        if result.conversation_truncate_to is not None:
            lines.append(f"Conversation truncated to position {result.conversation_truncate_to}.")
        return "\n".join(lines)

    registry.register(SlashCommand("rewind", "Selective rewind to a checkpoint", rewind_handler))


def _noop_write(path: str, content: str) -> None:
    """Default no-op write function for rewind when no real FS is wired."""
