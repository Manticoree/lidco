"""
Q94 CLI commands:
  /deps    [--unused] [--unpinned] [--no-vuln]
  /migrate list | apply <ruleset> [--write] [--path <glob>]
  /changelog [--since <tag>] [--version <label>] [--save]
  /env-check [--env <file>] [--template <file>] [--gen-template]
"""

from __future__ import annotations

import asyncio
import shlex
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.cli.commands.registry import CommandRegistry


def register_q94_commands(registry: "CommandRegistry") -> None:

    # ------------------------------------------------------------------ #
    # /deps
    # ------------------------------------------------------------------ #
    async def deps_handler(args: str) -> str:
        from lidco.dependencies.analyzer import DependencyAnalyzer

        parts = shlex.split(args) if args.strip() else []
        check_unused = "--no-unused" not in parts
        check_unpinned = "--no-unpinned" not in parts
        check_vuln = "--no-vuln" not in parts

        analyzer = DependencyAnalyzer(
            check_unused=check_unused,
            check_unpinned=check_unpinned,
            check_vulnerable=check_vuln,
        )
        try:
            report = analyzer.analyze()
        except Exception as exc:
            return f"Error analyzing dependencies: {exc}"

        if not report.packages:
            return (
                "No dependency manifests found.\n"
                "Supported: requirements*.txt, pyproject.toml, package.json"
            )

        lines = [
            f"Dependency Analysis — {report.summary()}",
            "",
            f"  Packages in manifest: {len(report.packages)}",
        ]

        if report.issues:
            lines += ["", "Issues:"]
            by_severity = {"high": [], "medium": [], "low": [], "info": []}
            for issue in report.issues:
                by_severity.setdefault(issue.severity, []).append(issue)

            for sev in ("high", "medium", "low", "info"):
                for issue in by_severity.get(sev, []):
                    icon = {"high": "🔴", "medium": "🟡", "low": "🔵", "info": "⚪"}.get(sev, "•")
                    lines.append(f"  {icon} [{sev:6s}] {issue.package}: {issue.description}")
        else:
            lines.append("  ✓ No issues found")

        return "\n".join(lines)

    registry.register_async(
        "deps",
        "Analyze dependencies for outdated/unused/vulnerable packages (Dependabot parity)",
        deps_handler,
    )

    # ------------------------------------------------------------------ #
    # /migrate
    # ------------------------------------------------------------------ #
    async def migrate_handler(args: str) -> str:
        from lidco.migration.engine import CodeMigrationEngine

        parts = shlex.split(args) if args.strip() else []
        subcommand = parts[0] if parts else "list"

        if subcommand == "list":
            engine = CodeMigrationEngine()
            rulesets = engine.list_rulesets()
            lines = ["Available migration rulesets:", ""]
            for name, count in rulesets.items():
                lines.append(f"  {name:12s}  {count} rules")
            lines += [
                "",
                "Usage: /migrate apply <ruleset> [--write]",
                "  --write  apply changes to disk (default: dry run)",
            ]
            return "\n".join(lines)

        if subcommand == "apply" and len(parts) >= 2:
            ruleset_name = parts[1]
            write = "--write" in parts
            dry_run = not write

            engine = CodeMigrationEngine(dry_run=dry_run)
            try:
                result = engine.apply_ruleset(ruleset_name)
            except KeyError as exc:
                return str(exc)
            except Exception as exc:
                return f"Migration error: {exc}"

            lines = [result.summary()]
            if result.files_changed:
                lines.append("")
                lines.append("Changed files:")
                for change in result.files_changed[:20]:
                    lines.append(f"  {change.path} ({change.match_count} replacements)")
                if len(result.files_changed) > 20:
                    lines.append(f"  … and {len(result.files_changed) - 20} more")
            if result.errors:
                lines.append("")
                lines.append("Errors:")
                for err in result.errors[:5]:
                    lines.append(f"  ✗ {err}")
            if dry_run and result.files_changed:
                lines.append("")
                lines.append("ℹ Run with --write to apply changes.")
            return "\n".join(lines)

        return (
            "Usage:\n"
            "  /migrate list\n"
            "  /migrate apply <ruleset> [--write]"
        )

    registry.register_async(
        "migrate",
        "Apply code migration rulesets (py2to3, stdlib, pytest) — Codemod parity",
        migrate_handler,
    )

    # ------------------------------------------------------------------ #
    # /changelog
    # ------------------------------------------------------------------ #
    async def changelog_handler(args: str) -> str:
        from lidco.git.changelog import ChangelogGenerator

        parts = shlex.split(args) if args.strip() else []
        since_tag: str | None = None
        version = "Unreleased"
        save = "--save" in parts

        i = 0
        while i < len(parts):
            if parts[i] == "--since" and i + 1 < len(parts):
                since_tag = parts[i + 1]
                i += 2
            elif parts[i] == "--version" and i + 1 < len(parts):
                version = parts[i + 1]
                i += 2
            else:
                i += 1

        generator = ChangelogGenerator(since_tag=since_tag, version=version)
        try:
            result = generator.generate()
        except Exception as exc:
            return f"Error generating changelog: {exc}"

        total_commits = sum(
            len(s.commits)
            for r in result.releases
            for s in r.sections
        )

        if total_commits == 0 and not result.unrecognized_commits:
            return "No conventional commits found. Use format: type: description"

        lines = [
            f"Changelog — {total_commits} conventional commits",
            f"Unrecognized (non-conventional): {len(result.unrecognized_commits)}",
        ]

        if save:
            try:
                path = generator.save(result)
                lines.append(f"Saved to: {path}")
            except Exception as exc:
                lines.append(f"Save error: {exc}")

        lines.append("")
        lines.append(result.to_markdown()[:3000])

        return "\n".join(lines)

    registry.register_async(
        "changelog",
        "Generate CHANGELOG from conventional commits (conventional-changelog parity)",
        changelog_handler,
    )

    # ------------------------------------------------------------------ #
    # /env-check
    # ------------------------------------------------------------------ #
    async def env_check_handler(args: str) -> str:
        from lidco.env.validator import EnvValidator

        parts = shlex.split(args) if args.strip() else []
        env_file = ".env"
        template_file: str | None = None
        gen_template = "--gen-template" in parts

        i = 0
        while i < len(parts):
            if parts[i] == "--env" and i + 1 < len(parts):
                env_file = parts[i + 1]
                i += 2
            elif parts[i] == "--template" and i + 1 < len(parts):
                template_file = parts[i + 1]
                i += 2
            else:
                i += 1

        validator = EnvValidator(env_file=env_file, template_file=template_file)

        if gen_template:
            try:
                path = validator.generate_template()
                return f"Generated template at: {path}"
            except FileNotFoundError as exc:
                return f"Error: {exc}"

        try:
            result = validator.validate()
        except Exception as exc:
            return f"Error validating env: {exc}"

        status = "✓ Valid" if result.is_valid else "✗ Invalid"
        lines = [
            f"Env Check — {status}",
            f"  {result.summary()}",
            f"  .env: {result.env_file}",
            f"  template: {result.template_file}",
        ]

        if result.issues:
            lines.append("")
            for issue in result.issues:
                icon = {"error": "🔴", "warning": "🟡", "info": "⚪"}.get(issue.severity, "•")
                name = f"[{issue.var_name}] " if issue.var_name else ""
                lines.append(f"  {icon} {name}{issue.description}")
        else:
            lines.append("  ✓ No issues found")

        return "\n".join(lines)

    registry.register_async(
        "env-check",
        "Validate .env against .env.example template (dotenv-vault parity)",
        env_check_handler,
    )
