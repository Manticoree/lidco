"""Q193 CLI commands: /vim, /keybindings, /macro, /repl-config."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:  # noqa: C901
    """Register Q193 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /vim
    # ------------------------------------------------------------------

    async def vim_handler(args: str) -> str:
        from lidco.input.vim_mode import VimEngine, VimMode

        parts = args.strip().split()
        if not parts:
            engine = _state.get("vim_engine")
            if engine is None:
                engine = VimEngine()
                _state["vim_engine"] = engine
            return f"Vim mode: {engine.mode.value} | cursor: {engine.state.cursor_pos}"

        sub = parts[0].lower()
        if sub in ("on", "enable"):
            engine = VimEngine()
            _state["vim_engine"] = engine
            return "Vim mode enabled (NORMAL)"
        if sub in ("off", "disable"):
            _state.pop("vim_engine", None)
            return "Vim mode disabled"
        if sub in ("normal", "insert", "visual", "command"):
            mode_map = {
                "normal": VimMode.NORMAL,
                "insert": VimMode.INSERT,
                "visual": VimMode.VISUAL,
                "command": VimMode.COMMAND,
            }
            engine = _state.get("vim_engine")
            if engine is None:
                engine = VimEngine()
            engine = engine.switch_mode(mode_map[sub])
            _state["vim_engine"] = engine
            return f"Switched to {sub.upper()} mode"
        return "Usage: /vim [on|off|normal|insert|visual|command]"

    # ------------------------------------------------------------------
    # /keybindings
    # ------------------------------------------------------------------

    async def keybindings_handler(args: str) -> str:
        from lidco.input.keybindings import KeybindingRegistry

        reg: KeybindingRegistry | None = _state.get("kb_registry")  # type: ignore[assignment]
        if reg is None:
            reg = KeybindingRegistry()
            _state["kb_registry"] = reg

        parts = args.strip().split(maxsplit=2)
        if not parts:
            if not reg.bindings:
                return "No keybindings configured."
            lines = [f"  {'+'.join(b.keys)} -> {b.action} ({b.context})" for b in reg.bindings]
            return "Keybindings:\n" + "\n".join(lines)

        sub = parts[0].lower()
        if sub == "bind" and len(parts) >= 3:
            keys = tuple(parts[1].split("+"))
            action = parts[2]
            reg = reg.bind(keys, action)
            _state["kb_registry"] = reg
            return f"Bound {parts[1]} -> {action}"
        if sub == "unbind" and len(parts) >= 2:
            keys = tuple(parts[1].split("+"))
            reg = reg.unbind(keys)
            _state["kb_registry"] = reg
            return f"Unbound {parts[1]}"
        if sub == "export":
            return reg.export_json()
        return "Usage: /keybindings [bind <keys> <action>|unbind <keys>|export]"

    # ------------------------------------------------------------------
    # /macro
    # ------------------------------------------------------------------

    async def macro_handler(args: str) -> str:
        from lidco.input.preprocessor import InputPreprocessor

        prep: InputPreprocessor | None = _state.get("preprocessor")  # type: ignore[assignment]
        if prep is None:
            prep = InputPreprocessor()
            _state["preprocessor"] = prep

        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /macro record <name> <keys>|replay <name>"

        sub = parts[0].lower()
        if sub == "record" and len(parts) >= 3:
            name = parts[1]
            keys = parts[2].split()
            macro = prep.record_macro(name, keys)
            return f"Recorded macro '{macro.name}' ({len(macro.keys)} keys)"
        if sub == "replay" and len(parts) >= 2:
            name = parts[1]
            if name not in prep._macros:
                return f"Macro '{name}' not found."
            macro = prep._macros[name]
            result = prep.replay_macro(macro)
            return f"Replayed '{name}': {' '.join(result)}"
        return "Usage: /macro record <name> <keys>|replay <name>"

    # ------------------------------------------------------------------
    # /repl-config
    # ------------------------------------------------------------------

    async def repl_config_handler(args: str) -> str:
        from lidco.input.repl_enhance import REPLEnhancer

        enhancer: REPLEnhancer | None = _state.get("enhancer")  # type: ignore[assignment]
        if enhancer is None:
            enhancer = REPLEnhancer()
            _state["enhancer"] = enhancer

        parts = args.strip().split()
        if not parts:
            return (
                f"Multiline: {enhancer._enable_multiline}\n"
                f"Highlight: {enhancer._enable_highlight}"
            )

        sub = parts[0].lower()
        if sub == "multiline":
            val = parts[1].lower() in ("on", "true", "1") if len(parts) > 1 else True
            enhancer = REPLEnhancer(enable_multiline=val, enable_highlight=enhancer._enable_highlight)
            _state["enhancer"] = enhancer
            return f"Multiline: {'on' if val else 'off'}"
        if sub == "highlight":
            val = parts[1].lower() in ("on", "true", "1") if len(parts) > 1 else True
            enhancer = REPLEnhancer(enable_multiline=enhancer._enable_multiline, enable_highlight=val)
            _state["enhancer"] = enhancer
            return f"Highlight: {'on' if val else 'off'}"
        return "Usage: /repl-config [multiline on|off|highlight on|off]"

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------

    registry.register(SlashCommand("vim", "Vim mode emulation for REPL", vim_handler))
    registry.register(SlashCommand("keybindings", "Manage keybindings", keybindings_handler))
    registry.register(SlashCommand("macro", "Record and replay macros", macro_handler))
    registry.register(SlashCommand("repl-config", "Configure REPL enhancements", repl_config_handler))
