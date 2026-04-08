"""
Q313 CLI commands — /snapshot, /snapshot-diff, /snapshot-review, /snapshot-stats

Registered via register_q313_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q313_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q313 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /snapshot — Create, list, show, update, delete snapshots
    # ------------------------------------------------------------------
    async def snapshot_handler(args: str) -> str:
        """
        Usage: /snapshot <subcommand> [options]
        Subcommands: list, show <name>, create <name> <value>, update <name> <value>, delete <name>
        """
        from lidco.snapshot_test.manager import SnapshotManager

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /snapshot <subcommand> [options]\n"
                "Subcommands: list, show <name>, create <name> <value>, "
                "update <name> <value>, delete <name>"
            )

        sub = parts[0]
        base_dir = "."

        # optional --dir
        i = 1
        while i < len(parts):
            if parts[i] == "--dir" and i + 1 < len(parts):
                base_dir = parts[i + 1]
                parts = parts[:i] + parts[i + 2:]
            else:
                i += 1

        mgr = SnapshotManager(base_dir)

        if sub == "list":
            names = mgr.list_snapshots()
            if not names:
                return "No snapshots found."
            return f"Snapshots ({len(names)}):\n" + "\n".join(f"  {n}" for n in names)

        if sub == "show":
            if len(parts) < 2:
                return "Usage: /snapshot show <name>"
            name = parts[1]
            rec = mgr.read(name)
            if rec is None:
                return f"Snapshot '{name}' not found."
            return (
                f"Snapshot: {rec.name}\n"
                f"Size: {rec.meta.size_bytes} bytes\n"
                f"Hash: {rec.meta.content_hash[:16]}...\n"
                f"---\n{rec.content}"
            )

        if sub == "create":
            if len(parts) < 3:
                return "Usage: /snapshot create <name> <value>"
            name = parts[1]
            value = " ".join(parts[2:])
            rec = mgr.create(name, value)
            return f"Created snapshot '{rec.name}' ({rec.meta.size_bytes} bytes)."

        if sub == "update":
            if len(parts) < 3:
                return "Usage: /snapshot update <name> <value>"
            name = parts[1]
            value = " ".join(parts[2:])
            rec = mgr.update(name, value)
            return f"Updated snapshot '{rec.name}' ({rec.meta.size_bytes} bytes)."

        if sub == "delete":
            if len(parts) < 2:
                return "Usage: /snapshot delete <name>"
            name = parts[1]
            ok = mgr.delete(name)
            if ok:
                return f"Deleted snapshot '{name}'."
            return f"Snapshot '{name}' not found."

        return f"Unknown subcommand: {sub}"

    registry.register_async("snapshot", "Create/list/show/update/delete snapshots", snapshot_handler)

    # ------------------------------------------------------------------
    # /snapshot-diff — Show diff between stored snapshot and new value
    # ------------------------------------------------------------------
    async def snapshot_diff_handler(args: str) -> str:
        """
        Usage: /snapshot-diff <name> <value> [--dir <dir>]
        """
        from lidco.snapshot_test.manager import SnapshotManager
        from lidco.snapshot_test.matcher import SnapshotMatcher

        parts = shlex.split(args) if args.strip() else []
        if len(parts) < 2:
            return "Usage: /snapshot-diff <name> <value> [--dir <dir>]"

        base_dir = "."
        i = 0
        while i < len(parts):
            if parts[i] == "--dir" and i + 1 < len(parts):
                base_dir = parts[i + 1]
                parts = parts[:i] + parts[i + 2:]
            else:
                i += 1

        if len(parts) < 2:
            return "Usage: /snapshot-diff <name> <value>"

        name = parts[0]
        value = " ".join(parts[1:])

        mgr = SnapshotManager(base_dir)
        matcher = SnapshotMatcher(mgr)
        diff = matcher.diff(name, value)
        if not diff:
            return f"No diff (snapshot '{name}' not found or identical)."
        return diff

    registry.register_async("snapshot-diff", "Show diff between snapshot and new value", snapshot_diff_handler)

    # ------------------------------------------------------------------
    # /snapshot-review — Review pending snapshot changes
    # ------------------------------------------------------------------
    async def snapshot_review_handler(args: str) -> str:
        """
        Usage: /snapshot-review [list|accept <name>|reject <name>|accept-all|reject-all|history] [--dir <dir>]
        """
        from lidco.snapshot_test.manager import SnapshotManager
        from lidco.snapshot_test.reviewer import SnapshotReviewer

        parts = shlex.split(args) if args.strip() else []

        base_dir = "."
        i = 0
        while i < len(parts):
            if parts[i] == "--dir" and i + 1 < len(parts):
                base_dir = parts[i + 1]
                parts = parts[:i] + parts[i + 2:]
            else:
                i += 1

        mgr = SnapshotManager(base_dir)
        reviewer = SnapshotReviewer(mgr)

        if not parts or parts[0] == "list":
            pending = reviewer.list_pending()
            if not pending:
                return "No pending snapshot reviews."
            lines = [f"Pending reviews ({len(pending)}):"]
            for item in pending:
                lines.append(f"  {item.name}")
            return "\n".join(lines)

        sub = parts[0]

        if sub == "accept" and len(parts) >= 2:
            name = parts[1]
            reviewer.add_pending(name, "")  # ensure it's tracked
            d = reviewer.accept(name)
            if d:
                return f"Accepted snapshot '{name}'."
            return f"No pending change for '{name}'."

        if sub == "reject" and len(parts) >= 2:
            name = parts[1]
            reviewer.add_pending(name, "")
            d = reviewer.reject(name)
            if d:
                return f"Rejected snapshot '{name}'."
            return f"No pending change for '{name}'."

        if sub == "accept-all":
            decisions = reviewer.accept_all()
            return f"Accepted {len(decisions)} snapshot(s)."

        if sub == "reject-all":
            decisions = reviewer.reject_all()
            return f"Rejected {len(decisions)} snapshot(s)."

        if sub == "history":
            hist = reviewer.get_history()
            if not hist:
                return "No review history."
            lines = [f"Review history ({len(hist)}):"]
            for d in hist:
                status = "accepted" if d.accepted else "rejected"
                lines.append(f"  {d.name}: {status}")
            return "\n".join(lines)

        return (
            "Usage: /snapshot-review [list|accept <name>|reject <name>|"
            "accept-all|reject-all|history] [--dir <dir>]"
        )

    registry.register_async("snapshot-review", "Review pending snapshot changes", snapshot_review_handler)

    # ------------------------------------------------------------------
    # /snapshot-stats — Snapshot analytics
    # ------------------------------------------------------------------
    async def snapshot_stats_handler(args: str) -> str:
        """
        Usage: /snapshot-stats [--stale-days N] [--dir <dir>]
        """
        from lidco.snapshot_test.analytics import SnapshotAnalytics
        from lidco.snapshot_test.manager import SnapshotManager

        parts = shlex.split(args) if args.strip() else []
        base_dir = "."
        stale_days: float | None = None

        i = 0
        while i < len(parts):
            if parts[i] == "--dir" and i + 1 < len(parts):
                base_dir = parts[i + 1]
                i += 2
            elif parts[i] == "--stale-days" and i + 1 < len(parts):
                try:
                    stale_days = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        mgr = SnapshotManager(base_dir)
        analytics = SnapshotAnalytics(mgr)

        st = analytics.stats()
        lines = [
            f"Snapshot Stats:",
            f"  Total: {st.total_snapshots}",
            f"  Total size: {st.total_size_bytes} bytes",
            f"  Avg size: {st.avg_size_bytes:.0f} bytes",
        ]
        if st.largest_name:
            lines.append(f"  Largest: {st.largest_name} ({st.largest_size} bytes)")
            lines.append(f"  Smallest: {st.smallest_name} ({st.smallest_size} bytes)")

        stale = analytics.stale_snapshots(days=stale_days)
        if stale:
            lines.append(f"\nStale snapshots ({len(stale)}):")
            for s in stale[:10]:
                lines.append(f"  {s.name}: {s.age_days:.0f} days old")

        churn = analytics.churn()
        if churn.entries:
            lines.append(f"\nChurn:")
            lines.append(f"  Avg updates: {churn.avg_updates:.1f}")
            if churn.most_churned:
                lines.append(f"  Most churned: {churn.most_churned}")

        return "\n".join(lines)

    registry.register_async("snapshot-stats", "Snapshot analytics and statistics", snapshot_stats_handler)
