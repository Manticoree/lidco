"""Q148 CLI commands: /maintenance clean/orphans/disk/health."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q148 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def maintenance_handler(args: str) -> str:
        from lidco.maintenance.temp_cleaner import TempCleaner
        from lidco.maintenance.orphan_detector import OrphanDetector
        from lidco.maintenance.disk_usage import DiskUsageAnalyzer
        from lidco.maintenance.workspace_health import WorkspaceHealth

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "clean":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else "."
            root = action if action else "."
            dry = False
            if len(sub_parts) > 1 and sub_parts[1].strip().lower() == "--dry-run":
                dry = True
            cleaner = TempCleaner()
            result = cleaner.clean(root, dry_run=dry)
            lines = [f"Removed: {len(result.removed)}, Skipped: {len(result.skipped)}, Freed: {result.bytes_freed} bytes"]
            if result.errors:
                lines.append(f"Errors: {len(result.errors)}")
            return "\n".join(lines)

        if sub == "estimate":
            root = rest.strip() or "."
            cleaner = TempCleaner()
            est = cleaner.estimate(root)
            return json.dumps(est, indent=2)

        if sub == "orphans":
            return "Provide file_list and import_map via API. CLI stub only."

        if sub == "disk":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else "."
            root = action if action else "."
            analyzer = DiskUsageAnalyzer()
            entries = analyzer.largest(root, n=10)
            return analyzer.format_tree(entries, max_depth=3)

        if sub == "health":
            wh = WorkspaceHealth()
            wh.add_metric("placeholder", lambda: (1.0, "OK"), weight=1.0)
            report = wh.evaluate()
            return WorkspaceHealth.format_report(report)

        return (
            "Usage: /maintenance <sub>\n"
            "  clean [root] [--dry-run]  -- remove temp files\n"
            "  estimate [root]           -- estimate cleanup size\n"
            "  orphans                   -- detect orphaned resources\n"
            "  disk [root]               -- disk usage analysis\n"
            "  health                    -- workspace health report"
        )

    registry.register(SlashCommand("maintenance", "Workspace cleanup & maintenance (Q148)", maintenance_handler))
