"""
Q326 CLI commands — /config-template, /config-validate, /config-diff, /config-audit

Registered via register_q326_commands(registry).
"""

from __future__ import annotations

import json
import shlex


def register_q326_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q326 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /config-template — Render config templates
    # ------------------------------------------------------------------
    async def config_template_handler(args: str) -> str:
        """
        Usage: /config-template <template-name> [--env ENV] [--var KEY=VAL ...]
        """
        from lidco.configmgmt.template import ConfigTemplateEngine

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /config-template <template-name> [--env ENV] [--var KEY=VAL ...]"

        template_name = parts[0]
        env: str | None = None
        overrides: dict[str, str] = {}

        i = 1
        while i < len(parts):
            if parts[i] == "--env" and i + 1 < len(parts):
                env = parts[i + 1]
                i += 2
            elif parts[i] == "--var" and i + 1 < len(parts):
                kv = parts[i + 1]
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    overrides[k] = v
                i += 2
            else:
                i += 1

        engine = ConfigTemplateEngine()
        # In a real scenario templates would be loaded from disk
        return f"Template '{template_name}' not found. Register templates first."

    registry.register_async(
        "config-template",
        "Render config files from templates with environment values",
        config_template_handler,
    )

    # ------------------------------------------------------------------
    # /config-validate — Validate config files
    # ------------------------------------------------------------------
    async def config_validate_handler(args: str) -> str:
        """
        Usage: /config-validate <path> [--schema SCHEMA]
        """
        from lidco.configmgmt.validator import ConfigValidator

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /config-validate <path> [--schema SCHEMA]"

        path = parts[0]
        schema_name: str | None = None

        i = 1
        while i < len(parts):
            if parts[i] == "--schema" and i + 1 < len(parts):
                schema_name = parts[i + 1]
                i += 2
            else:
                i += 1

        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except FileNotFoundError:
            return f"File not found: {path}"
        except OSError as exc:
            return f"Error reading file: {exc}"

        validator = ConfigValidator.with_defaults()
        result = validator.validate_json_string(text, schema_name=schema_name)

        if result.valid and not result.issues:
            return f"Config '{path}' is valid. ({result.checked_rules} rules checked)"

        lines = [f"Config '{path}': {'VALID' if result.valid else 'INVALID'} ({result.checked_rules} rules checked)"]
        for issue in result.issues:
            lines.append(f"  [{issue.severity.value}] {issue.path or '(root)'}: {issue.message}")
        return "\n".join(lines)

    registry.register_async(
        "config-validate",
        "Validate config files against schemas and best practices",
        config_validate_handler,
    )

    # ------------------------------------------------------------------
    # /config-diff — Diff configs between environments
    # ------------------------------------------------------------------
    async def config_diff_handler(args: str) -> str:
        """
        Usage: /config-diff <file1> <file2>
        """
        from lidco.configmgmt.diff import ConfigDiff

        parts = shlex.split(args) if args.strip() else []
        if len(parts) < 2:
            return "Usage: /config-diff <file1> <file2>"

        file1, file2 = parts[0], parts[1]

        try:
            with open(file1, "r", encoding="utf-8") as fh:
                cfg1 = json.loads(fh.read())
            with open(file2, "r", encoding="utf-8") as fh:
                cfg2 = json.loads(fh.read())
        except FileNotFoundError as exc:
            return f"File not found: {exc.filename}"
        except json.JSONDecodeError as exc:
            return f"Invalid JSON: {exc}"
        except OSError as exc:
            return f"Error reading file: {exc}"

        differ = ConfigDiff()
        result = differ.diff(cfg1, cfg2, source_name=file1, target_name=file2)
        return differ.summary(result)

    registry.register_async(
        "config-diff",
        "Diff config files between environments and highlight risks",
        config_diff_handler,
    )

    # ------------------------------------------------------------------
    # /config-audit — Config change audit log
    # ------------------------------------------------------------------
    async def config_audit_handler(args: str) -> str:
        """
        Usage: /config-audit [--config NAME] [--user USER] [--report]
        """
        from lidco.configmgmt.audit import ConfigAudit

        parts = shlex.split(args) if args.strip() else []
        config_name: str | None = None
        user: str | None = None
        report_mode = False

        i = 0
        while i < len(parts):
            if parts[i] == "--config" and i + 1 < len(parts):
                config_name = parts[i + 1]
                i += 2
            elif parts[i] == "--user" and i + 1 < len(parts):
                user = parts[i + 1]
                i += 2
            elif parts[i] == "--report":
                report_mode = True
                i += 1
            else:
                i += 1

        audit = ConfigAudit()

        if report_mode:
            rpt = audit.compliance_report()
            return (
                f"Compliance Report:\n"
                f"  Total changes: {rpt.total_changes}\n"
                f"  Configs modified: {', '.join(rpt.configs_modified) or 'none'}\n"
                f"  Period: {rpt.period_start or 'N/A'} .. {rpt.period_end or 'N/A'}"
            )

        entries = audit.get_history(config_name)
        if user:
            entries = [e for e in entries if e.user == user]

        if not entries:
            return "No audit entries found."

        lines = [f"Audit log ({len(entries)} entries):"]
        for e in entries:
            lines.append(
                f"  [{e.timestamp}] {e.action.value} {e.config_name} by {e.user}"
                + (f" — {e.reason}" if e.reason else "")
            )
        return "\n".join(lines)

    registry.register_async(
        "config-audit",
        "Track and audit config changes with compliance reporting",
        config_audit_handler,
    )
