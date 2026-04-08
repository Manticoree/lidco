"""
Q345 CLI commands — /api-freeze, /plugin-compat, /config-schema, /tool-integrity

Registered via register_q345_commands(registry).
"""
from __future__ import annotations

import json


def register_q345_commands(registry) -> None:
    """Register Q345 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /api-freeze
    # ------------------------------------------------------------------
    async def api_freeze_handler(args: str) -> str:
        """
        Usage: /api-freeze <json>
               /api-freeze demo
               /api-freeze --help

        Detect breaking changes between two API snapshots.
        JSON must have "old" and "new" keys, each containing
        {"functions": [{"name", "params", "return_type"}]}.
        """
        from lidco.stability.api_freeze import PublicApiFreezeChecker

        stripped = args.strip()
        if not stripped or stripped in ("--help", "-h"):
            return (
                "Usage: /api-freeze <json>\n"
                "  Detect breaking changes between two API versions.\n"
                "  JSON: {\"old\": {\"functions\": [...]}, "
                "\"new\": {\"functions\": [...]}}\n\n"
                "  /api-freeze demo — run a built-in demo"
            )

        checker = PublicApiFreezeChecker()

        if stripped == "demo":
            old_api = {
                "functions": [
                    {"name": "process", "params": ["data", "timeout"], "return_type": "str"},
                    {"name": "validate", "params": ["value"], "return_type": "bool"},
                ]
            }
            new_api = {
                "functions": [
                    {"name": "process", "params": ["data"], "return_type": "str"},
                    {"name": "validate", "params": ["value", "strict"], "return_type": "bool"},
                ]
            }
        else:
            try:
                payload = json.loads(stripped)
                old_api = payload.get("old", {})
                new_api = payload.get("new", {})
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"

        changes = checker.detect_breaking_changes(old_api, new_api)

        if not changes:
            return "No breaking changes detected between the two API versions."

        lines = [f"Found {len(changes)} change(s):\n"]
        for c in changes:
            severity_tag = f"[{c['severity']}]"
            lines.append(
                f"  {severity_tag} {c['function']} — {c['change_type']}: "
                f"{c['description']}"
            )
        return "\n".join(lines)

    registry.register_slash_command("api-freeze", api_freeze_handler)

    # ------------------------------------------------------------------
    # /plugin-compat
    # ------------------------------------------------------------------
    async def plugin_compat_handler(args: str) -> str:
        """
        Usage: /plugin-compat <json>
               /plugin-compat demo
               /plugin-compat --help

        Check plugin API compatibility with the host.
        JSON must have "plugin" and "host" keys, each containing
        {"version": str, "methods": [str]}.
        """
        from lidco.stability.plugin_compat import PluginApiCompatibility

        stripped = args.strip()
        if not stripped or stripped in ("--help", "-h"):
            return (
                "Usage: /plugin-compat <json>\n"
                "  Check plugin/host API compatibility.\n"
                "  JSON: {\"plugin\": {\"version\": \"1.0.0\", \"methods\": [...]},\n"
                "         \"host\":   {\"version\": \"1.0.0\", \"methods\": [...]}}\n\n"
                "  /plugin-compat demo — run a built-in demo"
            )

        compat = PluginApiCompatibility()

        if stripped == "demo":
            plugin_api = {"version": "1.2.0", "methods": ["init", "run", "shutdown"]}
            host_api = {"version": "1.0.0", "methods": ["init", "run", "shutdown", "health"]}
        else:
            try:
                payload = json.loads(stripped)
                plugin_api = payload.get("plugin", {})
                host_api = payload.get("host", {})
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"

        result = compat.check_compatibility(plugin_api, host_api)

        status = "COMPATIBLE" if result["compatible"] else "INCOMPATIBLE"
        lines = [
            f"Plugin compatibility: {status}",
            f"  Version match: {'yes' if result['version_ok'] else 'no'}",
        ]
        if result["missing_methods"]:
            lines.append(
                "  Missing methods (required by host): "
                + ", ".join(result["missing_methods"])
            )
        if result["extra_methods"]:
            lines.append(
                "  Extra methods (provided by plugin): "
                + ", ".join(result["extra_methods"])
            )
        return "\n".join(lines)

    registry.register_slash_command("plugin-compat", plugin_compat_handler)

    # ------------------------------------------------------------------
    # /config-schema
    # ------------------------------------------------------------------
    async def config_schema_handler(args: str) -> str:
        """
        Usage: /config-schema <json>
               /config-schema demo
               /config-schema --help

        Validate a config object against a schema.
        JSON must have "config" (dict) and "schema" keys.
        Schema: {"fields": [{"name", "type", "required", "default"?}]}.
        """
        from lidco.stability.config_schema import ConfigSchemaValidator

        stripped = args.strip()
        if not stripped or stripped in ("--help", "-h"):
            return (
                "Usage: /config-schema <json>\n"
                "  Validate config values against a schema.\n"
                "  JSON: {\"config\": {...}, \"schema\": "
                "{\"fields\": [{\"name\", \"type\", \"required\"}]}}\n\n"
                "  /config-schema demo — run a built-in demo"
            )

        validator = ConfigSchemaValidator()

        if stripped == "demo":
            schema = {
                "fields": [
                    {"name": "host", "type": "str", "required": True, "default": "localhost"},
                    {"name": "port", "type": "int", "required": True},
                    {"name": "debug", "type": "bool", "required": False, "default": False},
                ]
            }
            config = {"host": "example.com", "port": "8080", "debug": True, "unknown_key": 1}
        else:
            try:
                payload = json.loads(stripped)
                config = payload.get("config", {})
                schema = payload.get("schema", {})
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"

        lines: list[str] = []

        unknown = validator.reject_unknown_keys(config, schema)
        if unknown:
            lines.append(f"Unknown keys: {', '.join(unknown)}")

        defaults_report = validator.validate_defaults(schema)
        missing_defaults = [r for r in defaults_report if not r["has_default"]]
        if missing_defaults:
            lines.append(
                "Fields missing defaults: "
                + ", ".join(r["field"] for r in missing_defaults)
            )

        type_issues = validator.check_type_coercion(config, schema)
        for issue in type_issues:
            if not issue["coercible"]:
                lines.append(
                    f"Type error on '{issue['field']}': "
                    f"expected {issue['expected_type']}, "
                    f"got {issue['actual_type']}"
                )

        if not lines:
            return "Config schema validation passed — no issues found."
        return "Config schema issues:\n" + "\n".join(f"  - {l}" for l in lines)

    registry.register_slash_command("config-schema", config_schema_handler)

    # ------------------------------------------------------------------
    # /tool-integrity
    # ------------------------------------------------------------------
    async def tool_integrity_handler(args: str) -> str:
        """
        Usage: /tool-integrity <json>
               /tool-integrity demo
               /tool-integrity --help

        Check tool registry integrity.
        JSON must have "tools": [{\"name\", \"has_run\", \"has_description\",
        \"permissions\"}].
        """
        from lidco.stability.tool_integrity import ToolRegistryIntegrity

        stripped = args.strip()
        if not stripped or stripped in ("--help", "-h"):
            return (
                "Usage: /tool-integrity <json>\n"
                "  Verify tool registry completeness, uniqueness, and permissions.\n"
                "  JSON: {\"tools\": [{\"name\", \"has_run\": bool, "
                "\"has_description\": bool, \"permissions\": [...]}]}\n\n"
                "  /tool-integrity demo — run a built-in demo"
            )

        checker = ToolRegistryIntegrity()

        if stripped == "demo":
            tools = [
                {
                    "name": "file_read",
                    "has_run": True,
                    "has_description": True,
                    "permissions": ["read", "filesystem"],
                },
                {
                    "name": "shell_exec",
                    "has_run": True,
                    "has_description": False,
                    "permissions": ["execute", "shell"],
                },
                {
                    "name": "shell_exec",
                    "has_run": False,
                    "has_description": True,
                    "permissions": ["execute", "unknown_perm"],
                },
            ]
        else:
            try:
                payload = json.loads(stripped)
                tools = payload.get("tools", [])
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"

        lines: list[str] = []

        completeness = checker.check_completeness(tools)
        status = "complete" if completeness["complete"] else "incomplete"
        lines.append(
            f"Registry completeness: {status} "
            f"({completeness['total']} tool(s))"
        )
        if completeness["missing_run"]:
            lines.append(
                "  Missing _run: " + ", ".join(completeness["missing_run"])
            )
        if completeness["missing_description"]:
            lines.append(
                "  Missing description: "
                + ", ".join(completeness["missing_description"])
            )

        dupes = checker.find_duplicate_names(tools)
        if dupes:
            for d in dupes:
                lines.append(
                    f"  Duplicate name '{d['name']}' appears {d['count']} times "
                    f"at indices {d['indices']}"
                )

        perm_issues = checker.verify_permissions(tools)
        for p in perm_issues:
            for issue in p["issues"]:
                lines.append(f"  Permission issue: {issue}")

        return "\n".join(lines) if lines else "Tool registry integrity check passed."

    registry.register_slash_command("tool-integrity", tool_integrity_handler)
