"""Q127 CLI commands: /snapshot."""
from __future__ import annotations

_state: dict = {}


def register(registry) -> None:
    """Register Q127 commands."""
    from lidco.cli.commands.registry import SlashCommand

    async def snapshot_handler(args: str) -> str:
        from lidco.workspace.snapshot2 import WorkspaceSnapshotManager, WorkspaceSnapshot
        from lidco.workspace.change_tracker import ChangeTracker, FileChange

        if "manager" not in _state:
            _state["manager"] = WorkspaceSnapshotManager()
        if "snapshots" not in _state:
            _state["snapshots"] = {}
        if "tracker" not in _state:
            _state["tracker"] = ChangeTracker()

        manager: WorkspaceSnapshotManager = _state["manager"]
        snapshots: dict = _state["snapshots"]
        tracker: ChangeTracker = _state["tracker"]

        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "capture":
            label = parts[1] if len(parts) > 1 else "snapshot"
            paths_str = parts[2] if len(parts) > 2 else ""
            paths = [p.strip() for p in paths_str.split(",") if p.strip()] if paths_str else []
            snap = manager.capture(paths, label=label)
            snapshots[snap.id] = snap
            return (
                f"Captured snapshot '{snap.id}' (label='{snap.label}') "
                f"with {snap.file_count} file(s)."
            )

        if sub == "restore":
            if len(parts) < 2:
                return "Usage: /snapshot restore <id>"
            snap_id = parts[1]
            snap = snapshots.get(snap_id)
            if snap is None:
                return f"Snapshot '{snap_id}' not found."
            dry = len(parts) > 2 and parts[2].lower() == "dry"
            results = manager.restore(snap, dry_run=dry)
            ok = sum(1 for v in results.values() if v)
            prefix = "[dry-run] " if dry else ""
            return f"{prefix}Restored {ok}/{len(results)} file(s) from snapshot '{snap_id}'."

        if sub == "diff":
            if len(parts) < 3:
                return "Usage: /snapshot diff <id_a> <id_b>"
            id_a, id_b = parts[1], parts[2]
            snap_a = snapshots.get(id_a)
            snap_b = snapshots.get(id_b)
            if snap_a is None:
                return f"Snapshot '{id_a}' not found."
            if snap_b is None:
                return f"Snapshot '{id_b}' not found."
            result = manager.diff(snap_a, snap_b)
            lines = [f"Diff '{id_a}' vs '{id_b}':"]
            lines.append(f"  Added:     {result['added']}")
            lines.append(f"  Removed:   {result['removed']}")
            lines.append(f"  Modified:  {result['modified']}")
            lines.append(f"  Unchanged: {len(result['unchanged'])} file(s)")
            return "\n".join(lines)

        if sub == "list":
            if not snapshots:
                return "No snapshots captured."
            lines = [f"Snapshots ({len(snapshots)}):"]
            for sid, snap in snapshots.items():
                lines.append(
                    f"  {sid} — '{snap.label}' @ {snap.created_at} ({snap.file_count} files)"
                )
            return "\n".join(lines)

        return (
            "Usage: /snapshot <sub>\n"
            "  capture [label] [paths]   -- capture snapshot\n"
            "  restore <id> [dry]        -- restore from snapshot\n"
            "  diff <id_a> <id_b>        -- diff two snapshots\n"
            "  list                      -- list snapshots"
        )

    registry.register(SlashCommand("snapshot", "Workspace snapshot and restore", snapshot_handler))
