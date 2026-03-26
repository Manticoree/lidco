"""
Q95 CLI commands:
  /stats     [--top <n>] [--json]
  /todo      [--tag <TAG>] [--severity high|medium|low] [--blame]
  /licenses  [--project-license <spdx>] [--no-unknown]
  /hooks     list | install <name> <script> | remove <name> | enable <name> | disable <name> | run <name>
"""

from __future__ import annotations

import asyncio
import shlex
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.cli.commands.registry import CommandRegistry


def register_q95_commands(registry: "CommandRegistry") -> None:

    # ------------------------------------------------------------------ #
    # /stats
    # ------------------------------------------------------------------ #
    async def stats_handler(args: str) -> str:
        from lidco.stats.code_stats import CodeStats

        parts = shlex.split(args) if args.strip() else []
        top_n = 10
        as_json = "--json" in parts

        i = 0
        while i < len(parts):
            if parts[i] == "--top" and i + 1 < len(parts):
                try:
                    top_n = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        try:
            report = CodeStats().analyze()
        except Exception as exc:
            return f"Error: {exc}"

        if as_json:
            import json
            data = {
                lang: {
                    "files": s.files,
                    "code": s.code_lines,
                    "comments": s.comment_lines,
                    "blank": s.blank_lines,
                }
                for lang, s in report.by_language.items()
            }
            return json.dumps(data, indent=2)

        lines = [
            "Code Statistics",
            f"  {report.summary()}",
            "",
            f"  {'Language':<16} {'Files':>6} {'Code':>8} {'Comment':>9} {'Blank':>7}",
            f"  {'-'*16} {'-'*6} {'-'*8} {'-'*9} {'-'*7}",
        ]
        for stat in report.top_languages(top_n):
            lines.append(
                f"  {stat.language:<16} {stat.files:>6,} "
                f"{stat.code_lines:>8,} {stat.comment_lines:>9,} {stat.blank_lines:>7,}"
            )
        if report.skipped_files:
            lines.append(f"\n  (skipped {report.skipped_files} oversized files)")

        return "\n".join(lines)

    registry.register_async(
        "stats",
        "Count lines of code per language — cloc/tokei parity",
        stats_handler,
    )

    # ------------------------------------------------------------------ #
    # /todo
    # ------------------------------------------------------------------ #
    async def todo_handler(args: str) -> str:
        from lidco.analysis.todo_scanner import TodoScanner, TAG_SEVERITY

        parts = shlex.split(args) if args.strip() else []
        filter_tag: str | None = None
        filter_severity: str | None = None
        use_blame = "--blame" in parts

        i = 0
        while i < len(parts):
            if parts[i] == "--tag" and i + 1 < len(parts):
                filter_tag = parts[i + 1].upper()
                i += 2
            elif parts[i] == "--severity" and i + 1 < len(parts):
                filter_severity = parts[i + 1].lower()
                i += 2
            else:
                i += 1

        scanner = TodoScanner(use_git_blame=use_blame)
        try:
            report = scanner.scan()
        except Exception as exc:
            return f"Error scanning: {exc}"

        items = report.items
        if filter_tag:
            items = [i for i in items if i.tag == filter_tag]
        if filter_severity:
            items = [i for i in items if i.severity == filter_severity]

        if not items:
            return f"No TODO/FIXME items found ({report.files_scanned} files scanned)"

        lines = [
            f"TODO/FIXME Report — {report.summary()}",
            f"  (showing {len(items)} items, {report.files_scanned} files scanned)",
            "",
        ]

        sev_icon = {"high": "🔴", "medium": "🟡", "low": "🔵", "info": "⚪"}
        for item in sorted(items, key=lambda x: (x.severity, x.file, x.line)):
            icon = sev_icon.get(item.severity, "•")
            owner = f" [{item.owner}]" if item.owner else ""
            rel_path = item.file.replace("\\", "/")
            lines.append(f"  {icon} {item.tag}{owner} {rel_path}:{item.line}")
            lines.append(f"       {item.text[:120]}")

        by_tag = {}
        for item in report.items:
            by_tag[item.tag] = by_tag.get(item.tag, 0) + 1
        lines.append("")
        lines.append("By tag: " + "  ".join(f"{k}:{v}" for k, v in sorted(by_tag.items())))

        return "\n".join(lines)

    registry.register_async(
        "todo",
        "Scan codebase for TODO/FIXME/HACK comments (tech debt tracker)",
        todo_handler,
    )

    # ------------------------------------------------------------------ #
    # /licenses
    # ------------------------------------------------------------------ #
    async def licenses_handler(args: str) -> str:
        from lidco.compliance.license_checker import LicenseChecker

        parts = shlex.split(args) if args.strip() else []
        project_license = "MIT"
        flag_unknown = "--no-unknown" not in parts

        i = 0
        while i < len(parts):
            if parts[i] == "--project-license" and i + 1 < len(parts):
                project_license = parts[i + 1]
                i += 2
            else:
                i += 1

        checker = LicenseChecker(
            project_license=project_license,
            flag_unknown=flag_unknown,
        )
        try:
            report = checker.check()
        except Exception as exc:
            return f"Error checking licenses: {exc}"

        if not report.packages:
            return "No packages found. Is this a Python project with installed deps?"

        lines = [
            f"License Report — {report.summary()}",
            f"  Project license: {project_license}",
            "",
        ]

        by_class = report.by_classification
        for cls in ("copyleft", "weak_copyleft", "unknown", "permissive"):
            pkgs = by_class.get(cls, [])
            if not pkgs:
                continue
            icon = {"copyleft": "🔴", "weak_copyleft": "🟡", "unknown": "⚠️", "permissive": "✅"}.get(cls, "•")
            lines.append(f"  {icon} {cls.replace('_', '-').title()} ({len(pkgs)})")
            for pkg in sorted(pkgs, key=lambda p: p.name)[:10]:
                lines.append(f"       {pkg.name} {pkg.version} — {pkg.license}")
            if len(pkgs) > 10:
                lines.append(f"       … and {len(pkgs) - 10} more")
            lines.append("")

        if report.issues:
            lines.append("Issues:")
            for issue in report.issues:
                sev_icon = {"error": "🔴", "warning": "🟡"}.get(issue.severity, "⚪")
                lines.append(f"  {sev_icon} {issue.description}")

        return "\n".join(lines)

    registry.register_async(
        "licenses",
        "Check OSS license compliance of dependencies — FOSSA parity",
        licenses_handler,
    )

    # ------------------------------------------------------------------ #
    # /hooks
    # ------------------------------------------------------------------ #
    async def hooks_handler(args: str) -> str:
        from lidco.git.hooks_manager import HooksManager, STANDARD_HOOKS

        parts = shlex.split(args) if args.strip() else []
        subcommand = parts[0] if parts else "list"
        manager = HooksManager()

        if subcommand == "list":
            hooks = manager.list()
            if not hooks:
                return (
                    "No hooks installed in .git/hooks/\n"
                    "Usage: /hooks install <name> <script>"
                )
            lines = ["Git Hooks:", ""]
            for hook in sorted(hooks, key=lambda h: h.name):
                status = "✓ enabled " if hook.enabled else "✗ disabled"
                std = "" if hook.is_standard else " (custom)"
                lines.append(f"  {status}  {hook.name}{std}")
            lines += [
                "",
                "Standard hooks not installed:",
            ]
            installed_names = {h.name for h in hooks}
            missing = [n for n in STANDARD_HOOKS if n not in installed_names]
            if missing:
                lines.append("  " + ", ".join(missing[:8]))
            return "\n".join(lines)

        if subcommand == "install" and len(parts) >= 3:
            name = parts[1]
            script = " ".join(parts[2:])
            try:
                hook = manager.install(name, script)
                return f"✓ Installed hook '{hook.name}' at {hook.path}"
            except FileExistsError as exc:
                return f"Error: {exc}\nUse: /hooks install {name} <script> --overwrite"
            except Exception as exc:
                return f"Error installing hook: {exc}"

        if subcommand == "remove" and len(parts) >= 2:
            name = parts[1]
            removed = manager.remove(name)
            return f"✓ Removed hook '{name}'" if removed else f"Hook '{name}' not found"

        if subcommand == "enable" and len(parts) >= 2:
            try:
                hook = manager.enable(parts[1])
                return f"✓ Enabled hook '{hook.name}'"
            except Exception as exc:
                return f"Error: {exc}"

        if subcommand == "disable" and len(parts) >= 2:
            try:
                hook = manager.disable(parts[1])
                return f"✓ Disabled hook '{hook.name}'"
            except Exception as exc:
                return f"Error: {exc}"

        if subcommand == "run" and len(parts) >= 2:
            result = manager.run(parts[1])
            status = "✓ passed" if result.success else f"✗ failed (exit {result.returncode})"
            output = result.output[:1000] if result.output else "(no output)"
            return f"Hook '{result.hook_name}': {status}\n{output}"

        return (
            "Usage:\n"
            "  /hooks list\n"
            "  /hooks install <name> <script>\n"
            "  /hooks remove <name>\n"
            "  /hooks enable <name>\n"
            "  /hooks disable <name>\n"
            "  /hooks run <name>"
        )

    registry.register_async(
        "hooks",
        "Manage git hooks (pre-commit, pre-push, etc.) — husky/lefthook parity",
        hooks_handler,
    )
