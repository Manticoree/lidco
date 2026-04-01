"""Q205 CLI commands: /render-mode, /terminal-info, /status-line, /color."""

from __future__ import annotations


def register(registry) -> None:
    """Register Q205 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /render-mode
    # ------------------------------------------------------------------

    async def render_mode_handler(args: str) -> str:
        from lidco.terminal.render_engine import RenderEngine, RenderMode

        mode_str = args.strip().lower()
        if not mode_str:
            return (
                "Usage: /render-mode <mode>\n"
                "  normal      — standard output\n"
                "  alt_screen  — alternate screen buffer\n"
                "  minimal     — minimal rendering"
            )
        try:
            mode = RenderMode(mode_str)
        except ValueError:
            valid = ", ".join(m.value for m in RenderMode)
            return f"Unknown mode '{mode_str}'. Valid modes: {valid}"
        engine = RenderEngine(mode=mode)
        return f"Render mode set to {mode.value} ({engine.buffer.width}x{engine.buffer.height})"

    # ------------------------------------------------------------------
    # /terminal-info
    # ------------------------------------------------------------------

    async def terminal_info_handler(args: str) -> str:
        from lidco.terminal.detector import TerminalDetector

        detector = TerminalDetector()
        return detector.summary()

    # ------------------------------------------------------------------
    # /status-line
    # ------------------------------------------------------------------

    async def status_line_handler(args: str) -> str:
        from lidco.terminal.status_line import StatusLine

        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        sl = StatusLine()

        if sub == "set" and len(parts) >= 3:
            key, value = parts[1], parts[2]
            sl.set(key, value)
            return f"Status item '{key}' set to '{value}'"

        if sub == "demo":
            sl.set_model("claude-opus-4-20250901")
            sl.set_mode("normal")
            sl.set_tokens(1500, 200000)
            return sl.render()

        return (
            "Usage: /status-line <subcommand>\n"
            "  set <key> <value> — set a status item\n"
            "  demo              — show a demo status line"
        )

    # ------------------------------------------------------------------
    # /color
    # ------------------------------------------------------------------

    async def color_handler(args: str) -> str:
        from lidco.terminal.adaptive import AdaptiveRenderer

        renderer = AdaptiveRenderer()
        text = args.strip() or "Hello, world!"

        if not renderer.supports_color():
            return f"(no color support) {text}"
        return renderer.render_text(text, bold=True, color="green")

    registry.register(SlashCommand("render-mode", "Set terminal render mode", render_mode_handler))
    registry.register(SlashCommand("terminal-info", "Show terminal info", terminal_info_handler))
    registry.register(SlashCommand("status-line", "Manage status line", status_line_handler))
    registry.register(SlashCommand("color", "Render colored text", color_handler))
