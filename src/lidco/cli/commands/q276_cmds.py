"""Q276 CLI commands: /preset, /preset-library, /preset-compose, /preset-share."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:  # noqa: C901
    """Register Q276 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /preset
    # ------------------------------------------------------------------

    async def preset_handler(args: str) -> str:
        from lidco.presets.template import SessionTemplate, TemplateStore

        if "store" not in _state:
            _state["store"] = TemplateStore()
        store: TemplateStore = _state["store"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            templates = store.all_templates()
            if not templates:
                return "No templates registered."
            lines = [f"- {t.name}: {t.description} (v{t.version})" for t in templates]
            return "\n".join(lines)

        if sub == "get":
            if not rest:
                return "Usage: /preset get <name>"
            t = store.get(rest)
            if t is None:
                return f"Template '{rest}' not found."
            return f"{t.name} (v{t.version}): {t.description}\nTools: {', '.join(t.tools)}\nTags: {', '.join(t.tags)}"

        if sub == "create":
            create_parts = rest.split(maxsplit=1)
            if len(create_parts) < 2:
                return "Usage: /preset create <name> <json>"
            import json as _json
            try:
                data = _json.loads(create_parts[1])
            except _json.JSONDecodeError:
                return "Invalid JSON."
            tmpl = SessionTemplate(name=create_parts[0], **data)
            store.register(tmpl)
            return f"Template '{tmpl.name}' created."

        if sub == "remove":
            if not rest:
                return "Usage: /preset remove <name>"
            ok = store.remove(rest)
            return f"Template '{rest}' removed." if ok else f"Template '{rest}' not found."

        return "Usage: /preset [list | get <name> | create <name> <json> | remove <name>]"

    # ------------------------------------------------------------------
    # /preset-library
    # ------------------------------------------------------------------

    async def preset_library_handler(args: str) -> str:
        from lidco.presets.library import PresetLibrary

        if "lib" not in _state:
            _state["lib"] = PresetLibrary()
        lib: PresetLibrary = _state["lib"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            presets = lib.all_presets()
            if not presets:
                return "No presets available."
            lines = [f"- {p.name} [{p.category}] by {p.author}" for p in presets]
            return "\n".join(lines)

        if sub == "category":
            if not rest:
                return "Usage: /preset-library category <cat>"
            found = lib.by_category(rest)
            if not found:
                return f"No presets in category '{rest}'."
            lines = [f"- {p.name}: {p.template.description}" for p in found]
            return "\n".join(lines)

        if sub == "builtin":
            names = lib.builtin_names()
            return "Built-in presets: " + ", ".join(names)

        return "Usage: /preset-library [list | category <cat> | builtin]"

    # ------------------------------------------------------------------
    # /preset-compose
    # ------------------------------------------------------------------

    async def preset_compose_handler(args: str) -> str:
        from lidco.presets.library import PresetLibrary
        from lidco.presets.composer import PresetComposer

        if "lib" not in _state:
            _state["lib"] = PresetLibrary()
        lib: PresetLibrary = _state["lib"]  # type: ignore[assignment]
        composer = PresetComposer(lib)

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "extend":
            ep = rest.split(maxsplit=2)
            if len(ep) < 3:
                return "Usage: /preset-compose extend <base> <overrides_json> <new_name>"
            import json as _json
            try:
                overrides = _json.loads(ep[1])
            except _json.JSONDecodeError:
                return "Invalid JSON for overrides."
            try:
                tmpl = composer.extend(ep[0], overrides, ep[2])
            except KeyError as exc:
                return str(exc)
            return f"Extended '{ep[0]}' -> '{tmpl.name}'."

        if sub == "merge":
            mp = rest.split()
            if len(mp) < 3:
                return "Usage: /preset-compose merge <a> <b> <new_name>"
            try:
                tmpl = composer.merge(mp[0], mp[1], mp[2])
            except KeyError as exc:
                return str(exc)
            return f"Merged '{mp[0]}' + '{mp[1]}' -> '{tmpl.name}'."

        if sub == "preview":
            if not rest:
                return "Usage: /preset-compose preview <name>"
            try:
                text = composer.preview(rest)
            except KeyError as exc:
                return str(exc)
            return text

        return "Usage: /preset-compose [extend <base> <overrides_json> <new> | merge <a> <b> <new> | preview <name>]"

    # ------------------------------------------------------------------
    # /preset-share
    # ------------------------------------------------------------------

    async def preset_share_handler(args: str) -> str:
        from lidco.presets.library import PresetLibrary
        from lidco.presets.sharing import PresetSharing, SharedPreset

        if "lib" not in _state:
            _state["lib"] = PresetLibrary()
        lib: PresetLibrary = _state["lib"]  # type: ignore[assignment]
        if "sharing" not in _state:
            _state["sharing"] = PresetSharing(lib)
        sharing: PresetSharing = _state["sharing"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "export":
            if not rest:
                return "Usage: /preset-share export <name>"
            try:
                shared = sharing.export_preset(rest)
            except KeyError as exc:
                return str(exc)
            return f"Exported '{shared.name}' (checksum={shared.checksum})."

        if sub == "import":
            if not rest:
                return "Usage: /preset-share import <json>"
            import json as _json
            try:
                data = _json.loads(rest)
                sp = SharedPreset(**data)
            except (TypeError, _json.JSONDecodeError):
                return "Invalid SharedPreset JSON."
            ok = sharing.import_preset(sp)
            return f"Imported '{sp.name}'." if ok else f"Import failed for '{sp.name}' (conflict or bad checksum)."

        if sub == "verify":
            if not rest:
                return "Usage: /preset-share verify <json>"
            import json as _json
            try:
                data = _json.loads(rest)
                sp = SharedPreset(**data)
            except (TypeError, _json.JSONDecodeError):
                return "Invalid SharedPreset JSON."
            ok = sharing.verify(sp)
            return f"Checksum valid." if ok else "Checksum INVALID."

        if sub == "list":
            shared_list = sharing.shared_presets()
            if not shared_list:
                return "No shared presets."
            lines = [f"- {s.name} by {s.author} (checksum={s.checksum})" for s in shared_list]
            return "\n".join(lines)

        return "Usage: /preset-share [export <name> | import <json> | verify <json> | list]"

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------
    registry.register(SlashCommand("preset", "Session template management", preset_handler))
    registry.register(SlashCommand("preset-library", "Browse preset library", preset_library_handler))
    registry.register(SlashCommand("preset-compose", "Compose and extend presets", preset_compose_handler))
    registry.register(SlashCommand("preset-share", "Share and import presets", preset_share_handler))
