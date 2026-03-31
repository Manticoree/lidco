"""Q144 CLI commands: /config-migrate."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q144 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def config_migrate_handler(args: str) -> str:
        from lidco.config.config_version import ConfigVersion
        from lidco.config.config_migrator import ConfigMigrator
        from lidco.config.config_backup import ConfigBackup
        from lidco.config.compat_checker import CompatChecker

        if "cv" not in _state:
            _state["cv"] = ConfigVersion()
        if "migrator" not in _state:
            _state["migrator"] = ConfigMigrator()
        if "backup" not in _state:
            _state["backup"] = ConfigBackup()
        if "checker" not in _state:
            _state["checker"] = CompatChecker()

        cv: ConfigVersion = _state["cv"]  # type: ignore[assignment]
        migrator: ConfigMigrator = _state["migrator"]  # type: ignore[assignment]
        backup: ConfigBackup = _state["backup"]  # type: ignore[assignment]
        checker: CompatChecker = _state["checker"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "version":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "stamp":
                if len(sub_parts) < 2:
                    return "Usage: /config-migrate version stamp <version> <json_data>"
                stamp_parts = sub_parts[1].split(maxsplit=1)
                ver = stamp_parts[0]
                try:
                    data = json.loads(stamp_parts[1]) if len(stamp_parts) > 1 else {}
                except json.JSONDecodeError:
                    return "Invalid JSON."
                vc = cv.stamp(data, ver)
                return f"Stamped config at version {vc.version}."
            if action == "get":
                if len(sub_parts) < 2:
                    return "Usage: /config-migrate version get <json_data>"
                try:
                    data = json.loads(sub_parts[1])
                except json.JSONDecodeError:
                    return "Invalid JSON."
                v = cv.get_version(data)
                return f"Version: {v}" if v else "No version found."
            if action == "compare":
                if len(sub_parts) < 2:
                    return "Usage: /config-migrate version compare <v1> <v2>"
                cmp_parts = sub_parts[1].split()
                if len(cmp_parts) < 2:
                    return "Usage: /config-migrate version compare <v1> <v2>"
                try:
                    r = cv.compare_versions(cmp_parts[0], cmp_parts[1])
                except ValueError as e:
                    return str(e)
                return f"compare({cmp_parts[0]}, {cmp_parts[1]}) = {r}"
            return "Usage: /config-migrate version stamp|get|compare"

        if sub == "migrate":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "run":
                if len(sub_parts) < 2:
                    return "Usage: /config-migrate migrate run <target_version> <json_data>"
                run_parts = sub_parts[1].split(maxsplit=1)
                target = run_parts[0]
                try:
                    data = json.loads(run_parts[1]) if len(run_parts) > 1 else {}
                except json.JSONDecodeError:
                    return "Invalid JSON."
                result = migrator.migrate(data, target)
                return (
                    f"Migration {'OK' if result.success else 'FAILED'}: "
                    f"{result.from_version} -> {result.to_version}, "
                    f"{result.steps_applied} steps"
                    + (f", errors: {result.errors}" if result.errors else "")
                )
            if action == "dry-run":
                if len(sub_parts) < 2:
                    return "Usage: /config-migrate migrate dry-run <target_version> <json_data>"
                run_parts = sub_parts[1].split(maxsplit=1)
                target = run_parts[0]
                try:
                    data = json.loads(run_parts[1]) if len(run_parts) > 1 else {}
                except json.JSONDecodeError:
                    return "Invalid JSON."
                result = migrator.dry_run(data, target)
                return (
                    f"Dry-run {'OK' if result.success else 'FAILED'}: "
                    f"{result.from_version} -> {result.to_version}, "
                    f"{result.steps_applied} steps"
                )
            if action == "path":
                if len(sub_parts) < 2:
                    return "Usage: /config-migrate migrate path <from> <to>"
                path_parts = sub_parts[1].split()
                if len(path_parts) < 2:
                    return "Usage: /config-migrate migrate path <from> <to>"
                path = migrator.migration_path(path_parts[0], path_parts[1])
                if not path:
                    return f"No path from {path_parts[0]} to {path_parts[1]}."
                lines = [f"Migration path ({len(path)} steps):"]
                for s in path:
                    lines.append(f"  {s.from_version} -> {s.to_version}: {s.description}")
                return "\n".join(lines)
            return "Usage: /config-migrate migrate run|dry-run|path"

        if sub == "backup":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "create":
                if len(sub_parts) < 2:
                    return "Usage: /config-migrate backup create <version> [label] <json_data>"
                remainder = sub_parts[1]
                # First token is version
                ver_rest = remainder.split(maxsplit=1)
                ver = ver_rest[0]
                after_ver = ver_rest[1] if len(ver_rest) > 1 else ""
                # Find JSON start (first '{' or '[')
                label = None
                json_start = -1
                for i, ch in enumerate(after_ver):
                    if ch in ('{', '['):
                        json_start = i
                        break
                if json_start == -1:
                    data = {}
                    lbl_text = after_ver.strip()
                    if lbl_text:
                        label = lbl_text
                else:
                    lbl_text = after_ver[:json_start].strip()
                    if lbl_text:
                        label = lbl_text
                    data_str = after_ver[json_start:]
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        return "Invalid JSON."
                entry = backup.backup(data, ver, label)
                return f"Backup created: {entry.id[:8]} (v{entry.version})"
            if action == "list":
                entries = backup.list_backups()
                if not entries:
                    return "No backups."
                lines = [f"Backups ({len(entries)}):"]
                for e in entries:
                    lbl = f" [{e.label}]" if e.label else ""
                    lines.append(f"  {e.id[:8]} v{e.version}{lbl}")
                return "\n".join(lines)
            if action == "restore":
                if len(sub_parts) < 2:
                    return "Usage: /config-migrate backup restore <id>"
                bid = sub_parts[1].strip()
                # Support partial id
                match = None
                for e in backup.list_backups():
                    if e.id.startswith(bid):
                        match = e
                        break
                if match is None:
                    return f"Backup '{bid}' not found."
                data = backup.restore(match.id)
                return f"Restored backup {match.id[:8]}."
            if action == "delete":
                if len(sub_parts) < 2:
                    return "Usage: /config-migrate backup delete <id>"
                bid = sub_parts[1].strip()
                match = None
                for e in backup.list_backups():
                    if e.id.startswith(bid):
                        match = e
                        break
                if match is None:
                    return f"Backup '{bid}' not found."
                backup.delete(match.id)
                return f"Deleted backup {match.id[:8]}."
            return "Usage: /config-migrate backup create|list|restore|delete"

        if sub == "compat":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "check":
                if len(sub_parts) < 2:
                    return "Usage: /config-migrate compat check <json_data>"
                try:
                    data = json.loads(sub_parts[1])
                except json.JSONDecodeError:
                    return "Invalid JSON."
                result = checker.check(data)
                if result.compatible and not result.issues:
                    return "Config is compatible. No issues found."
                lines = [f"Compatible: {result.compatible}, issues: {len(result.issues)}"]
                for iss in result.issues:
                    lines.append(f"  [{iss.severity}] {iss.field}: {iss.message}")
                if result.suggestions:
                    lines.append("Suggestions:")
                    for s in result.suggestions:
                        lines.append(f"  - {s}")
                return "\n".join(lines)
            if action == "fix":
                if len(sub_parts) < 2:
                    return "Usage: /config-migrate compat fix <json_data>"
                try:
                    data = json.loads(sub_parts[1])
                except json.JSONDecodeError:
                    return "Invalid JSON."
                fixed, actions = checker.auto_fix(data)
                if not actions:
                    return "No fixes needed."
                lines = [f"Applied {len(actions)} fix(es):"]
                for a in actions:
                    lines.append(f"  - {a}")
                return "\n".join(lines)
            return "Usage: /config-migrate compat check|fix"

        return (
            "Usage: /config-migrate <sub>\n"
            "  version stamp|get|compare    -- version management\n"
            "  migrate run|dry-run|path     -- migration pipeline\n"
            "  backup create|list|restore|delete -- config backups\n"
            "  compat check|fix             -- compatibility checking"
        )

    registry.register(SlashCommand("config-migrate", "Config migration & versioning (Q144)", config_migrate_handler))
