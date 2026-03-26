"""Q102 CLI commands: /container /plugins /flags /audit."""
from __future__ import annotations

_state: dict[str, object] = {}


def _get_container():
    from lidco.core.container import Container
    if "container" not in _state:
        _state["container"] = Container()
    return _state["container"]


def _get_registry():
    from lidco.plugins.registry import PluginRegistry
    if "plugin_registry" not in _state:
        _state["plugin_registry"] = PluginRegistry()
    return _state["plugin_registry"]


def _get_flags():
    from lidco.features.flags import FeatureFlags
    if "flags" not in _state:
        _state["flags"] = FeatureFlags(path=None)
    return _state["flags"]


def _get_audit():
    from lidco.audit.logger import AuditLogger
    if "audit" not in _state:
        _state["audit"] = AuditLogger(path=None)
    return _state["audit"]


def register(registry) -> None:
    """Register Q102 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def container_handler(args: str) -> str:
        """Usage: /container <register name value | resolve name | list | clear>"""
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /container <register name value | resolve name | list | clear>"
        c = _get_container()
        cmd = parts[0].lower()
        if cmd == "register":
            if len(parts) < 3:
                return "Usage: /container register <name> <value>"
            c.register(parts[1], parts[2])
            return f"Registered: {parts[1]!r}"
        elif cmd == "resolve":
            if len(parts) < 2:
                return "Usage: /container resolve <name>"
            try:
                val = c.resolve(parts[1])
                return f"{parts[1]} = {val!r}"
            except KeyError as e:
                return f"Error: {e}"
            except Exception as e:
                return f"Error: {e}"
        elif cmd == "list":
            names = c.names()
            return "\n".join(names) if names else "(empty)"
        elif cmd == "clear":
            c.clear()
            return "Container cleared."
        elif cmd == "registered":
            return str(c.is_registered(parts[1]) if len(parts) > 1 else "(provide name)")
        return f"Unknown subcommand: {cmd}"

    async def plugins_handler(args: str) -> str:
        """Usage: /plugins <list | load <path> | info <name> | clear>"""
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Usage: /plugins <list | load <path> | info <name> | clear>"
        reg = _get_registry()
        cmd = parts[0].lower()
        if cmd == "list":
            names = reg.list()
            if not names:
                return "(no plugins registered)"
            lines = []
            for name, meta in reg.list_with_metadata():
                lines.append(f"  {name} v{meta.version} — {meta.description or '(no description)'}")
            return "\n".join(lines)
        elif cmd == "load":
            if len(parts) < 2:
                return "Usage: /plugins load <directory>"
            from pathlib import Path
            p = Path(parts[1])
            if not p.exists():
                return f"Path not found: {p}"
            loaded = reg.load_all(p)
            return f"Loaded {len(loaded)} plugin(s): {', '.join(loaded) or '(none)'}"
        elif cmd == "info":
            if len(parts) < 2:
                return "Usage: /plugins info <name>"
            from lidco.plugins.registry import PluginNotFoundError
            try:
                meta = reg.get_metadata(parts[1])
                return (
                    f"name={meta.name}  version={meta.version}\n"
                    f"author={meta.author or '(unknown)'}\n"
                    f"description={meta.description or '(none)'}"
                )
            except PluginNotFoundError:
                return f"Plugin {parts[1]!r} not found."
        elif cmd == "clear":
            reg.clear()
            return "Plugin registry cleared."
        return f"Unknown subcommand: {cmd}"

    async def flags_handler(args: str) -> str:
        """Usage: /flags <list | define name [--rollout N] | enable name | disable name | check name [id] | remove name>"""
        parts = args.strip().split()
        if not parts:
            return "Usage: /flags <list | define name | enable name | disable name | check name [id] | remove name>"
        f = _get_flags()
        cmd = parts[0].lower()
        if cmd == "list":
            names = f.list_flags()
            if not names:
                return "(no flags defined)"
            lines = []
            for name in names:
                cfg = f.get_config(name)
                status = "ON" if cfg.enabled else "OFF"
                lines.append(f"  {name} [{status}] rollout={cfg.rollout:.0f}%")
            return "\n".join(lines)
        elif cmd == "define":
            if len(parts) < 2:
                return "Usage: /flags define <name> [--rollout <pct>]"
            name = parts[1]
            rollout = 0.0
            if "--rollout" in parts:
                idx = parts.index("--rollout")
                try:
                    rollout = float(parts[idx + 1])
                except (IndexError, ValueError):
                    pass
            f.define(name, enabled=True, rollout=rollout)
            return f"Defined flag {name!r} (rollout={rollout:.0f}%)"
        elif cmd == "enable":
            if len(parts) < 2:
                return "Usage: /flags enable <name>"
            from lidco.features.flags import FeatureFlagNotFoundError
            try:
                cfg = f.get_config(parts[1])
                f.define(parts[1], enabled=True, rollout=cfg.rollout,
                         allowlist=cfg.allowlist, denylist=cfg.denylist)
                return f"Enabled: {parts[1]}"
            except FeatureFlagNotFoundError:
                return f"Flag {parts[1]!r} not found."
        elif cmd == "disable":
            if len(parts) < 2:
                return "Usage: /flags disable <name>"
            from lidco.features.flags import FeatureFlagNotFoundError
            try:
                cfg = f.get_config(parts[1])
                f.define(parts[1], enabled=False, rollout=cfg.rollout,
                         allowlist=cfg.allowlist, denylist=cfg.denylist)
                return f"Disabled: {parts[1]}"
            except FeatureFlagNotFoundError:
                return f"Flag {parts[1]!r} not found."
        elif cmd == "check":
            if len(parts) < 2:
                return "Usage: /flags check <name> [identifier]"
            identifier = parts[2] if len(parts) > 2 else ""
            enabled = f.is_enabled(parts[1], identifier)
            return f"{parts[1]} for {identifier!r}: {'ENABLED' if enabled else 'DISABLED'}"
        elif cmd == "remove":
            if len(parts) < 2:
                return "Usage: /flags remove <name>"
            removed = f.remove(parts[1])
            return f"Removed: {removed}"
        return f"Unknown subcommand: {cmd}"

    async def audit_handler(args: str) -> str:
        """Usage: /audit <log actor action resource | query [--actor X] | stats | export csv|json | clear>"""
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Usage: /audit <log actor action resource | query | stats | export csv|json | clear>"
        al = _get_audit()
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        if cmd == "log":
            tokens = rest.split(maxsplit=2)
            if len(tokens) < 3:
                return "Usage: /audit log <actor> <action> <resource>"
            entry = al.log(tokens[0], tokens[1], tokens[2])
            return f"Logged [{entry.id[:8]}] {entry.actor} / {entry.action} / {entry.resource} → {entry.outcome}"
        elif cmd == "query":
            entries = al.query(limit=20)
            if not entries:
                return "(no entries)"
            import datetime
            lines = []
            for e in entries:
                ts = datetime.datetime.fromtimestamp(e.timestamp).strftime("%H:%M:%S")
                lines.append(f"  [{ts}] {e.actor} {e.action} {e.resource} → {e.outcome}")
            return "\n".join(lines)
        elif cmd == "stats":
            total = al.count()
            entries = al.all()
            outcomes: dict[str, int] = {}
            for e in entries:
                outcomes[e.outcome] = outcomes.get(e.outcome, 0) + 1
            lines = [f"Total entries: {total}"]
            for k, v in sorted(outcomes.items()):
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        elif cmd == "export":
            fmt = rest.strip().lower() or "json"
            if fmt == "csv":
                return al.export_csv()
            return al.export_json()
        elif cmd == "clear":
            n = al.clear()
            return f"Cleared {n} audit entries."
        return f"Unknown subcommand: {cmd}"

    registry.register(SlashCommand("container", "DI container management", container_handler))
    registry.register(SlashCommand("plugins", "Plugin registry management", plugins_handler))
    registry.register(SlashCommand("flags", "Feature flag management", flags_handler))
    registry.register(SlashCommand("audit", "Audit log management", audit_handler))
