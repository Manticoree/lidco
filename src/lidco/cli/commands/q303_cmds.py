"""Q303 CLI commands — /branch-strategy, /branch-cleanup, /branch-dashboard, /worktree

Registered via register_q303_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q303_commands(registry) -> None:
    """Register Q303 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /branch-strategy [set <name> | validate <branch> | create <type> <name> | rules | prefixes]
    # ------------------------------------------------------------------
    async def branch_strategy_handler(args: str) -> str:
        from lidco.branches.strategy import BranchStrategy2

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "rules"
        s = BranchStrategy2()

        if subcmd == "set":
            if len(parts) < 2:
                return "Usage: /branch-strategy set <gitflow|github-flow|trunk-based>"
            try:
                s.set_strategy(parts[1])
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Strategy set to '{parts[1]}'."

        if subcmd == "validate":
            if len(parts) < 2:
                return "Usage: /branch-strategy validate <branch-name>"
            valid = s.validate_name(parts[1])
            return f"'{parts[1]}' is {'valid' if valid else 'invalid'} under {s.strategy}."

        if subcmd == "create":
            if len(parts) < 3:
                return "Usage: /branch-strategy create <type> <name>"
            try:
                branch = s.auto_create(parts[1], parts[2])
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Branch name: {branch}"

        if subcmd == "prefixes":
            return ", ".join(s.allowed_prefixes())

        # default: rules
        rules = s.naming_rules()
        lines = [
            f"Strategy: {rules['strategy']}",
            f"Pattern: {rules['pattern']}",
            f"Protected: {', '.join(rules['protected'])}",
            f"Prefixes: {', '.join(rules['prefixes'])}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /branch-cleanup [stale [days] | merged | orphaned | delete <names...> | protect <names...>]
    # ------------------------------------------------------------------
    async def branch_cleanup_handler(args: str) -> str:
        from lidco.branches.cleanup import BranchCleanup

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "stale"
        c = BranchCleanup()

        if subcmd == "stale":
            days = int(parts[1]) if len(parts) > 1 else 30
            stale = c.stale(days)
            if not stale:
                return "No stale branches found."
            return "Stale branches:\n" + "\n".join(f"  {b}" for b in stale)

        if subcmd == "merged":
            merged = c.merged()
            if not merged:
                return "No merged branches found."
            return "Merged branches:\n" + "\n".join(f"  {b}" for b in merged)

        if subcmd == "orphaned":
            orphaned = c.orphaned()
            if not orphaned:
                return "No orphaned branches found."
            return "Orphaned branches:\n" + "\n".join(f"  {b}" for b in orphaned)

        if subcmd == "delete":
            names = parts[1:]
            if not names:
                return "Usage: /branch-cleanup delete <branch1> [branch2...]"
            count = c.bulk_delete(names)
            return f"Deleted {count} branch(es)."

        if subcmd == "protect":
            names = parts[1:]
            if not names:
                return "Usage: /branch-cleanup protect <branch1> [branch2...]"
            c.protected(names)
            return f"Protected {len(names)} branch(es)."

        return (
            "Usage: /branch-cleanup <subcommand>\n"
            "  stale [days]          list stale branches\n"
            "  merged                list merged branches\n"
            "  orphaned              list orphaned branches\n"
            "  delete <names...>     delete branches\n"
            "  protect <names...>    mark as protected"
        )

    # ------------------------------------------------------------------
    # /branch-dashboard [overview | authors | merge-status | summary]
    # ------------------------------------------------------------------
    async def branch_dashboard_handler(args: str) -> str:
        from lidco.branches.dashboard import BranchDashboard2

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "summary"
        d = BranchDashboard2()

        if subcmd == "overview":
            ov = d.overview()
            if not ov:
                return "No branches tracked."
            lines = []
            for b in ov:
                lines.append(f"  {b['name']} +{b['ahead']}/-{b['behind']} ({b['author']})")
            return "Branch overview:\n" + "\n".join(lines)

        if subcmd == "authors":
            authors = d.active_authors()
            if not authors:
                return "No authors found."
            return "Active authors:\n" + "\n".join(f"  {a}" for a in authors)

        if subcmd == "merge-status":
            ms = d.merge_status()
            lines = [
                f"Ahead only: {ms['ahead_only']}",
                f"Behind only: {ms['behind_only']}",
                f"Diverged: {ms['diverged']}",
                f"Up to date: {ms['up_to_date']}",
            ]
            return "\n".join(lines)

        # default: summary
        s = d.summary()
        return (
            f"Total branches: {s['total']}\n"
            f"Active authors: {s['authors']}\n"
            f"Merge status: {s['merge_status']}"
        )

    # ------------------------------------------------------------------
    # /worktree [create <branch> [path] | remove <path> | list | cleanup | usage | cache]
    # ------------------------------------------------------------------
    async def worktree_handler(args: str) -> str:
        from lidco.branches.worktree_v2 import WorktreeManagerV2

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "list"
        mgr = WorktreeManagerV2()

        if subcmd == "create":
            if len(parts) < 2:
                return "Usage: /worktree create <branch> [path]"
            branch = parts[1]
            path = parts[2] if len(parts) > 2 else None
            try:
                wt = mgr.create(branch, path)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Created worktree for '{wt.branch}' at {wt.path}"

        if subcmd == "remove":
            if len(parts) < 2:
                return "Usage: /worktree remove <path>"
            ok = mgr.remove(parts[1])
            return f"Removed: {ok}"

        if subcmd == "list":
            wts = mgr.list_worktrees()
            if not wts:
                return "No worktrees."
            lines = [f"  {w.branch} -> {w.path}" for w in wts]
            return "Worktrees:\n" + "\n".join(lines)

        if subcmd == "cleanup":
            count = mgr.auto_cleanup()
            return f"Cleaned up {count} worktree(s)."

        if subcmd == "usage":
            usage = mgr.disk_usage()
            if not usage:
                return "No worktrees to measure."
            lines = [f"  {p}: {b} bytes" for p, b in usage.items()]
            return "Disk usage:\n" + "\n".join(lines)

        if subcmd == "cache":
            return f"Shared cache: {mgr.shared_cache_path()}"

        return (
            "Usage: /worktree <subcommand>\n"
            "  create <branch> [path]  create worktree\n"
            "  remove <path>           remove worktree\n"
            "  list                    list all worktrees\n"
            "  cleanup                 auto-cleanup old worktrees\n"
            "  usage                   show disk usage\n"
            "  cache                   show shared cache path"
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("branch-strategy", "Branch naming strategy", branch_strategy_handler))
    registry.register(SlashCommand("branch-cleanup", "Branch cleanup utilities", branch_cleanup_handler))
    registry.register(SlashCommand("branch-dashboard", "Branch dashboard overview", branch_dashboard_handler))
    registry.register(SlashCommand("worktree", "Git worktree management", worktree_handler))
