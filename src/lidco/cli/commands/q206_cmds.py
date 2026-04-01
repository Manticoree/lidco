"""Q206 CLI commands: /screenshot, /click, /type-text, /visual-test."""
from __future__ import annotations

from typing import Any

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q206 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /screenshot
    # ------------------------------------------------------------------

    async def screenshot_handler(args: str) -> str:
        from lidco.computer_use.screenshot import ScreenRegion, ScreenshotAnalyzer

        if "analyzer" not in _state:
            _state["analyzer"] = ScreenshotAnalyzer()
        analyzer: ScreenshotAnalyzer = _state["analyzer"]  # type: ignore[assignment]

        parts = args.strip().split()
        if parts and parts[0] == "region" and len(parts) == 5:
            try:
                x, y, w, h = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                region = ScreenRegion(x=x, y=y, width=w, height=h)
                result = analyzer.capture(region)
                return f"Captured region {w}x{h} at ({x},{y}), format={result.format}"
            except ValueError:
                return "Usage: /screenshot region <x> <y> <width> <height>"

        if parts and parts[0] == "history":
            hist = analyzer.history()
            if not hist:
                return "No screenshots captured."
            lines = [f"{len(hist)} screenshot(s):"]
            for i, s in enumerate(hist):
                lines.append(f"  [{i}] {s.width}x{s.height} {s.format}")
            return "\n".join(lines)

        result = analyzer.capture()
        return f"Captured {result.width}x{result.height} screenshot, format={result.format}"

    # ------------------------------------------------------------------
    # /click
    # ------------------------------------------------------------------

    async def click_handler(args: str) -> str:
        from lidco.computer_use.controller import ScreenController

        if "controller" not in _state:
            _state["controller"] = ScreenController()
        ctrl: ScreenController = _state["controller"]  # type: ignore[assignment]

        parts = args.strip().split()
        if len(parts) < 2:
            return "Usage: /click <x> <y> [button]"
        try:
            x, y = int(parts[0]), int(parts[1])
        except ValueError:
            return "Usage: /click <x> <y> [button]"

        button = parts[2] if len(parts) > 2 else "left"
        coord = ctrl.click(x, y, button)
        return f"Clicked ({coord.x},{coord.y}) button={button}"

    # ------------------------------------------------------------------
    # /type-text
    # ------------------------------------------------------------------

    async def type_text_handler(args: str) -> str:
        from lidco.computer_use.controller import ScreenController

        if "controller" not in _state:
            _state["controller"] = ScreenController()
        ctrl: ScreenController = _state["controller"]  # type: ignore[assignment]

        text = args.strip()
        if not text:
            return "Usage: /type-text <text>"
        typed = ctrl.type_text(text)
        return f"Typed: {typed}"

    # ------------------------------------------------------------------
    # /visual-test
    # ------------------------------------------------------------------

    async def visual_test_handler(args: str) -> str:
        from lidco.computer_use.visual_test import VisualTestRunner

        if "vt_runner" not in _state:
            _state["vt_runner"] = VisualTestRunner()
        runner: VisualTestRunner = _state["vt_runner"]  # type: ignore[assignment]

        sub = args.strip().lower()

        if sub == "summary":
            return runner.summary()

        if sub == "results":
            results = runner.results()
            if not results:
                return "No visual test results."
            lines = [f"{len(results)} test(s):"]
            for r in results:
                status = "PASS" if r.passed else "FAIL"
                lines.append(f"  [{status}] {r.test_name}")
            return "\n".join(lines)

        return (
            "Usage: /visual-test <subcommand>\n"
            "  summary   — show test summary\n"
            "  results   — list test results"
        )

    registry.register(SlashCommand("screenshot", "Capture simulated screenshot", screenshot_handler))
    registry.register(SlashCommand("click", "Simulate mouse click", click_handler))
    registry.register(SlashCommand("type-text", "Simulate keyboard input", type_text_handler))
    registry.register(SlashCommand("visual-test", "Visual test runner", visual_test_handler))
