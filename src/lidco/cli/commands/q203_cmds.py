"""Q203 CLI commands: /managed-settings, /policy, /settings-hierarchy, /admin."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q203 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /managed-settings
    # ------------------------------------------------------------------

    async def managed_settings_handler(args: str) -> str:
        from lidco.enterprise.managed_settings import ManagedSettingsLoader

        if "settings_loader" not in _state:
            _state["settings_loader"] = ManagedSettingsLoader()
        loader: ManagedSettingsLoader = _state["settings_loader"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "load":
            if not rest:
                return "Usage: /managed-settings load <path>"
            try:
                data = loader.load_file(rest)
                return f"Loaded {len(data)} top-level keys from {rest}."
            except Exception as exc:
                return f"Error: {exc}"

        if sub == "get":
            if not rest:
                return "Usage: /managed-settings get <key>"
            value = loader.get(rest)
            if value is None:
                return f"Key '{rest}' not found."
            return json.dumps(value, indent=2) if isinstance(value, (dict, list)) else str(value)

        if sub == "load-managed":
            try:
                data = loader.load_managed()
                return f"Loaded managed settings: {len(data)} top-level keys."
            except Exception as exc:
                return f"Error: {exc}"

        return (
            "Usage: /managed-settings <subcommand>\n"
            "  load <path>      — load a JSON file\n"
            "  get <key>        — get value by dot-notation key\n"
            "  load-managed     — load managed-settings.json + managed-settings.d/"
        )

    # ------------------------------------------------------------------
    # /policy
    # ------------------------------------------------------------------

    async def policy_handler(args: str) -> str:
        from lidco.enterprise.policy_enforcer import Policy, PolicyAction, PolicyEnforcer

        if "enforcer" not in _state:
            _state["enforcer"] = PolicyEnforcer()
        enforcer: PolicyEnforcer = _state["enforcer"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            policies = enforcer.list_policies()
            if not policies:
                return "No policies registered."
            lines = [f"{len(policies)} policy(ies):"]
            for p in policies:
                lines.append(f"  {p.name}: {p.resource} -> {p.action.value}")
            return "\n".join(lines)

        if sub == "check":
            if not rest:
                return "Usage: /policy check <resource>"
            action = enforcer.check(rest)
            return f"Resource '{rest}': {action.value}"

        if sub == "violations":
            vs = enforcer.violations()
            if not vs:
                return "No violations recorded."
            lines = [f"{len(vs)} violation(s):"]
            for v in vs:
                lines.append(f"  {v.policy_name}: {v.resource} -> {v.action.value}")
            return "\n".join(lines)

        if sub == "summary":
            return enforcer.summary()

        return (
            "Usage: /policy <subcommand>\n"
            "  list             — list all policies\n"
            "  check <resource> — check policy for resource\n"
            "  violations       — show recorded violations\n"
            "  summary          — show summary"
        )

    # ------------------------------------------------------------------
    # /settings-hierarchy
    # ------------------------------------------------------------------

    async def settings_hierarchy_handler(args: str) -> str:
        from lidco.enterprise.settings_hierarchy import SettingsHierarchy

        if "hierarchy" not in _state:
            _state["hierarchy"] = SettingsHierarchy()
        hierarchy: SettingsHierarchy = _state["hierarchy"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "layers":
            layers = hierarchy.list_layers()
            if not layers:
                return "No layers configured."
            lines = [f"{len(layers)} layer(s):"]
            for l in layers:
                lines.append(f"  {l.name} (priority={l.priority}): {len(l.data)} keys")
            return "\n".join(lines)

        if sub == "resolve":
            if not rest:
                return "Usage: /settings-hierarchy resolve <key>"
            value = hierarchy.resolve(rest)
            if value is None:
                return f"Key '{rest}' not found."
            return json.dumps(value, indent=2) if isinstance(value, (dict, list)) else str(value)

        if sub == "summary":
            return hierarchy.summary()

        return (
            "Usage: /settings-hierarchy <subcommand>\n"
            "  layers           — list configured layers\n"
            "  resolve <key>    — resolve a setting by key\n"
            "  summary          — show summary"
        )

    # ------------------------------------------------------------------
    # /admin
    # ------------------------------------------------------------------

    async def admin_handler(args: str) -> str:
        from lidco.enterprise.admin_controls import AdminControls

        if "admin" not in _state:
            _state["admin"] = AdminControls()
        admin: AdminControls = _state["admin"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "disable-plugin":
            if not rest:
                return "Usage: /admin disable-plugin <name> [reason]"
            name_parts = rest.split(maxsplit=1)
            name = name_parts[0]
            reason = name_parts[1] if len(name_parts) > 1 else ""
            admin.disable_plugin(name, reason)
            return f"Disabled plugin '{name}'."

        if sub == "enable-plugin":
            if not rest:
                return "Usage: /admin enable-plugin <name>"
            admin.enable_plugin(rest)
            return f"Enabled plugin '{rest}'."

        if sub == "disabled-plugins":
            plugins = admin.disabled_plugins()
            if not plugins:
                return "No disabled plugins."
            return "Disabled plugins: " + ", ".join(plugins)

        if sub == "audit":
            log = admin.audit_log()
            if not log:
                return "No admin actions recorded."
            lines = [f"{len(log)} admin action(s):"]
            for a in log:
                lines.append(f"  {a.action}: {a.target}")
            return "\n".join(lines)

        if sub == "summary":
            return admin.summary()

        return (
            "Usage: /admin <subcommand>\n"
            "  disable-plugin <name> [reason]  — disable a plugin\n"
            "  enable-plugin <name>            — enable a plugin\n"
            "  disabled-plugins                — list disabled plugins\n"
            "  audit                           — show audit log\n"
            "  summary                         — show summary"
        )

    registry.register(SlashCommand("managed-settings", "Managed settings loader", managed_settings_handler))
    registry.register(SlashCommand("policy", "Policy enforcement", policy_handler))
    registry.register(SlashCommand("settings-hierarchy", "Settings hierarchy", settings_hierarchy_handler))
    registry.register(SlashCommand("admin", "Admin controls", admin_handler))
