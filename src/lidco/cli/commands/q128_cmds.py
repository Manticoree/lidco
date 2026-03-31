"""Q128 CLI commands: /profile."""
from __future__ import annotations

import json

_state: dict = {}


def register(registry) -> None:
    """Register Q128 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def profile_handler(args: str) -> str:
        from lidco.config.profile import ProfileManager

        if "mgr" not in _state:
            _storage: dict = {}

            def _write_fn(path: str, data: str) -> None:
                _storage[path] = data

            def _read_fn(path: str) -> str:
                if path not in _storage:
                    raise FileNotFoundError(path)
                return _storage[path]

            _state["storage"] = _storage
            _state["mgr"] = ProfileManager(
                store_path="/tmp/lidco_profiles_q128.json",
                write_fn=_write_fn,
                read_fn=_read_fn,
            )
        mgr: ProfileManager = _state["mgr"]

        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "list":
            profiles = mgr.list_all()
            if not profiles:
                return "No profiles defined."
            lines = ["Profiles:"]
            for p in profiles:
                marker = "*" if p.is_active else " "
                lines.append(f"  {marker} {p.name}: {p.description}")
            return "\n".join(lines)

        if sub == "create":
            if len(parts) < 2:
                return "Usage: /profile create <name> [json_settings]"
            name = parts[1]
            settings: dict = {}
            if len(parts) > 2:
                try:
                    settings = json.loads(parts[2])
                except json.JSONDecodeError:
                    return "Invalid JSON settings."
            p = mgr.create(name, settings)
            return f"Created profile '{p.name}'."

        if sub == "activate":
            if len(parts) < 2:
                return "Usage: /profile activate <name>"
            name = parts[1]
            try:
                p = mgr.activate(name)
                return f"Activated profile '{p.name}'."
            except KeyError as exc:
                return str(exc)

        if sub == "delete":
            if len(parts) < 2:
                return "Usage: /profile delete <name>"
            name = parts[1]
            ok = mgr.delete(name)
            return f"Deleted profile '{name}'." if ok else f"Profile '{name}' not found."

        if sub == "show":
            if len(parts) < 2:
                return "Usage: /profile show <name>"
            name = parts[1]
            p = mgr.get(name)
            if p is None:
                return f"Profile '{name}' not found."
            return json.dumps(vars(p), indent=2)

        if sub == "export":
            return mgr.export()

        if sub == "import":
            if len(parts) < 2:
                return "Usage: /profile import <json_string>"
            try:
                count = mgr.import_profiles(parts[1])
                return f"Imported {count} profile(s)."
            except Exception as exc:
                return f"Import failed: {exc}"

        return (
            "Usage: /profile <sub>\n"
            "  list                         -- list all profiles\n"
            "  create <name> [json]         -- create profile\n"
            "  activate <name>              -- activate profile\n"
            "  delete <name>                -- delete profile\n"
            "  show <name>                  -- show profile\n"
            "  export                       -- export all profiles as JSON\n"
            "  import <json>                -- import profiles from JSON"
        )

    registry.register(SlashCommand("profile", "Manage configuration profiles", profile_handler))
