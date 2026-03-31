"""Q141 CLI commands: /recovery."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q141 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def recovery_handler(args: str) -> str:
        from lidco.resilience.auto_checkpoint import AutoCheckpoint
        from lidco.resilience.session_repairer import SessionRepairer
        from lidco.resilience.crash_recovery import CrashRecovery

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "checkpoint":
            cp_store: AutoCheckpoint = _state.get("checkpoint_store")  # type: ignore[assignment]
            if cp_store is None:
                cp_store = AutoCheckpoint()
                _state["checkpoint_store"] = cp_store

            sub2_parts = rest.strip().split(maxsplit=1)
            action = sub2_parts[0].lower() if sub2_parts and sub2_parts[0] else "list"
            action_rest = sub2_parts[1] if len(sub2_parts) > 1 else ""

            if action == "save":
                label = action_rest or "manual"
                cp = cp_store.save(label, {"source": "cli"})
                return f"Checkpoint saved: {cp.id} ({cp.label})"

            if action == "list":
                cps = cp_store.list_checkpoints()
                if not cps:
                    return "No checkpoints."
                lines = [f"Checkpoints ({len(cps)}):"]
                for c in cps:
                    lines.append(f"  {c.id[:8]}  {c.label}  ({c.size_bytes}B)")
                return "\n".join(lines)

            if action == "restore":
                cp_id = action_rest.strip()
                if not cp_id:
                    return "Usage: /recovery checkpoint restore <id>"
                data = cp_store.restore(cp_id)
                if data is None:
                    return "Checkpoint not found."
                return json.dumps(data, indent=2)

            if action == "clear":
                cp_store.clear()
                return "All checkpoints cleared."

            return (
                "Usage: /recovery checkpoint <action>\n"
                "  save [label]     -- save checkpoint\n"
                "  list             -- list checkpoints\n"
                "  restore <id>     -- restore checkpoint\n"
                "  clear            -- clear all"
            )

        if sub == "repair":
            repairer = SessionRepairer()
            try:
                data = json.loads(rest) if rest else {}
            except json.JSONDecodeError:
                return "Invalid JSON for repair."
            result = repairer.repair(data)
            if not result.repaired:
                return "Session data is valid, no repairs needed."
            lines = [f"Repaired ({len(result.actions)} actions):"]
            for a in result.actions:
                lines.append(f"  {a.field}: {a.issue} -> {a.action}")
            if result.warnings:
                lines.append("Warnings:")
                for w in result.warnings:
                    lines.append(f"  {w}")
            return "\n".join(lines)

        if sub == "recover":
            cp_store = _state.get("checkpoint_store")  # type: ignore[assignment]
            if cp_store is None:
                cp_store = AutoCheckpoint()
                _state["checkpoint_store"] = cp_store
            recovery = CrashRecovery(cp_store)
            data = recovery.recover()
            if data is None:
                return "No checkpoint data available for recovery."
            return json.dumps(data, indent=2)

        if sub == "status":
            cp_store = _state.get("checkpoint_store")  # type: ignore[assignment]
            if cp_store is None:
                cp_store = AutoCheckpoint()
                _state["checkpoint_store"] = cp_store
            count = len(cp_store.list_checkpoints())
            latest = cp_store.latest()
            lines = [f"Checkpoints: {count}"]
            if latest:
                lines.append(f"Latest: {latest.id[:8]} ({latest.label})")
            else:
                lines.append("Latest: none")
            return "\n".join(lines)

        return (
            "Usage: /recovery <sub>\n"
            "  checkpoint <action>  -- manage checkpoints\n"
            "  repair <json>        -- repair session data\n"
            "  recover              -- recover from last checkpoint\n"
            "  status               -- show recovery status"
        )

    registry.register(
        SlashCommand("recovery", "Session resilience & crash recovery (Q141)", recovery_handler)
    )
