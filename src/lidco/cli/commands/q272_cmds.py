"""Q272 CLI commands: /a11y, /high-contrast, /reduced-motion, /voice."""
from __future__ import annotations


def register(registry) -> None:  # noqa: D401
    """Register Q272 accessibility commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # Shared singleton instances (created lazily on first use).
    _instances: dict = {}

    def _sr():
        if "sr" not in _instances:
            from lidco.a11y.screen_reader import ScreenReaderSupport
            _instances["sr"] = ScreenReaderSupport()
        return _instances["sr"]

    def _hc():
        if "hc" not in _instances:
            from lidco.a11y.high_contrast import HighContrastMode
            _instances["hc"] = HighContrastMode()
        return _instances["hc"]

    def _rm():
        if "rm" not in _instances:
            from lidco.a11y.reduced_motion import ReducedMotion
            _instances["rm"] = ReducedMotion()
        return _instances["rm"]

    def _vc():
        if "vc" not in _instances:
            from lidco.a11y.voice_control import VoiceControl
            _instances["vc"] = VoiceControl()
        return _instances["vc"]

    # ------------------------------------------------------------------
    # /a11y
    # ------------------------------------------------------------------

    async def a11y_handler(args: str) -> str:
        parts = args.strip().split()
        sub = parts[0].lower() if parts else "status"

        if sub == "status":
            lines = [
                f"screen-reader: {'enabled' if _sr().is_enabled() else 'disabled'}",
                f"high-contrast: {'enabled' if _hc().is_enabled() else 'disabled'}",
                f"reduced-motion: {'enabled' if _rm().is_enabled() else 'disabled'}",
                f"voice-control: {'enabled' if _vc().is_enabled() else 'disabled'}",
            ]
            return "\n".join(lines)

        if sub == "enable" and len(parts) >= 2:
            feat = parts[1].lower()
            dispatch = {
                "screen-reader": _sr().enable,
                "high-contrast": _hc().enable,
                "reduced-motion": _rm().enable,
                "voice-control": _vc().enable,
            }
            fn = dispatch.get(feat)
            if fn is None:
                return f"Unknown feature: {feat}"
            fn()
            return f"{feat} enabled."

        if sub == "disable" and len(parts) >= 2:
            feat = parts[1].lower()
            dispatch = {
                "screen-reader": _sr().disable,
                "high-contrast": _hc().disable,
                "reduced-motion": _rm().disable,
                "voice-control": _vc().disable,
            }
            fn = dispatch.get(feat)
            if fn is None:
                return f"Unknown feature: {feat}"
            fn()
            return f"{feat} disabled."

        return (
            "Usage: /a11y [status | enable <feature> | disable <feature>]\n"
            "Features: screen-reader, high-contrast, reduced-motion, voice-control"
        )

    # ------------------------------------------------------------------
    # /high-contrast
    # ------------------------------------------------------------------

    async def high_contrast_handler(args: str) -> str:
        parts = args.strip().split()
        sub = parts[0].lower() if parts else ""

        if sub == "enable":
            _hc().enable()
            return "High contrast mode enabled."

        if sub == "disable":
            _hc().disable()
            return "High contrast mode disabled."

        if sub == "check" and len(parts) >= 3:
            pair = _hc().check_contrast(parts[1], parts[2])
            return (
                f"Ratio: {pair.ratio}\n"
                f"AA: {'pass' if pair.passes_aa else 'fail'}\n"
                f"AAA: {'pass' if pair.passes_aaa else 'fail'}"
            )

        if sub == "palette":
            pal = _hc().palette()
            return "\n".join(f"{k}: {v}" for k, v in pal.items())

        return (
            "Usage: /high-contrast [enable | disable | check <fg> <bg> | palette]"
        )

    # ------------------------------------------------------------------
    # /reduced-motion
    # ------------------------------------------------------------------

    async def reduced_motion_handler(args: str) -> str:
        parts = args.strip().split()
        sub = parts[0].lower() if parts else "status"

        if sub == "enable":
            _rm().enable()
            return "Reduced motion enabled."

        if sub == "disable":
            _rm().disable()
            return "Reduced motion disabled."

        if sub == "status":
            s = _rm().summary()
            lines = [f"{k}: {v}" for k, v in s.items()]
            return "\n".join(lines)

        if sub == "preference" and len(parts) >= 3:
            key = parts[1]
            val = parts[2].lower() in ("true", "1", "yes")
            try:
                _rm().set_preference(key, val)
            except ValueError as exc:
                return str(exc)
            return f"{key} set to {val}."

        return (
            "Usage: /reduced-motion [enable | disable | status | preference <key> <bool>]"
        )

    # ------------------------------------------------------------------
    # /voice
    # ------------------------------------------------------------------

    async def voice_handler(args: str) -> str:
        parts = args.strip().split()
        sub = parts[0].lower() if parts else ""

        if sub == "enable":
            _vc().enable()
            return "Voice control enabled."

        if sub == "disable":
            _vc().disable()
            return "Voice control disabled."

        if sub == "add" and len(parts) >= 3:
            phrase = parts[1]
            action = parts[2]
            cat = parts[3] if len(parts) >= 4 else "navigation"
            cmd = _vc().register_command(phrase, action, cat)
            return f"Registered: {cmd.phrase} -> {cmd.action} [{cmd.category}]"

        if sub == "match" and len(parts) >= 2:
            text = " ".join(parts[1:])
            cmd = _vc().match(text)
            if cmd is None:
                return "No match."
            return f"Matched: {cmd.phrase} -> {cmd.action} [{cmd.category}]"

        if sub == "list":
            cmds = _vc().commands()
            if not cmds:
                return "No commands registered."
            return "\n".join(f"{c.phrase} -> {c.action} [{c.category}]" for c in cmds)

        return (
            "Usage: /voice [enable | disable | add <phrase> <action> | match <text> | list]"
        )

    registry.register(SlashCommand("a11y", "Accessibility feature management", a11y_handler))
    registry.register(SlashCommand("high-contrast", "High contrast mode", high_contrast_handler))
    registry.register(SlashCommand("reduced-motion", "Reduced motion preferences", reduced_motion_handler))
    registry.register(SlashCommand("voice", "Voice control management", voice_handler))
