"""CLI commands for browser automation and visual testing (Q88)."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.cli.commands.registry import CommandRegistry


def register_browser_commands(registry: "CommandRegistry") -> None:
    """Register /browser, /visual-test, /plan-act, /screenshot commands."""

    async def browser_handler(args: str) -> str:
        parts = args.strip().split(None, 1)
        sub = parts[0] if parts else "help"
        rest = parts[1] if len(parts) > 1 else ""
        try:
            from lidco.browser.browser_session import BrowserSession, BrowserAction
            session = BrowserSession()
            if not session.is_available:
                return "Playwright not installed. Run: pip install playwright && playwright install chromium"
            if sub == "navigate" and rest:
                results = await session.run_actions([BrowserAction(kind="navigate", url=rest)])
                return results[0].output if results else "No result"
            elif sub == "screenshot":
                results = await session.run_actions([BrowserAction(kind="screenshot")])
                r = results[0] if results else None
                if r and r.success:
                    return f"Screenshot captured ({len(r.screenshot_b64)} chars base64)"
                return r.error if r else "No result"
            return "Usage: /browser [navigate <url>|screenshot]"
        except Exception as e:
            return f"/browser failed: {e}"

    async def visual_test_handler(args: str) -> str:
        parts = args.strip().split(None, 1)
        sub = parts[0] if parts else "list"
        try:
            from lidco.browser.visual_test_runner import VisualTestRunner, VisualTestCase
            runner = VisualTestRunner()
            if sub == "list":
                baselines = runner.list_baselines()
                if not baselines:
                    return "No visual baselines yet. Run tests to create them."
                return "Baselines: " + ", ".join(baselines)
            elif sub == "run" and len(parts) > 1:
                name = parts[1].strip()
                test = VisualTestCase(name=name, url="")
                # Use dummy 1x1 white PNG bytes for demo
                dummy = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
                result = runner.run_test(test, dummy)
                return f"Test '{name}': {'PASSED' if result.passed else 'FAILED'}" + (" [new baseline]" if result.is_new_baseline else "")
            return "Usage: /visual-test [list|run <name>]"
        except Exception as e:
            return f"/visual-test failed: {e}"

    async def plan_act_handler(args: str) -> str:
        parts = args.strip().split(None, 1)
        sub = parts[0] if parts else "help"
        rest = parts[1] if len(parts) > 1 else ""
        try:
            from lidco.agents.plan_act_controller import PlanActController
            ctrl = PlanActController()
            if sub == "plan" and rest:
                steps = [{"description": s.strip()} for s in rest.split("|") if s.strip()]
                ctrl.build_plan(steps)
                return ctrl.format_plan()
            elif sub == "act" and rest:
                steps_raw = [{"description": s.strip()} for s in rest.split("|") if s.strip()]
                result = await ctrl.plan_then_act(steps_raw, auto_approve=True)
                return result.format_summary()
            elif sub == "mode":
                return f"Current mode: {ctrl.mode}"
            return "Usage: /plan-act [plan <step1>|<step2>|... | act <steps> | mode]"
        except Exception as e:
            return f"/plan-act failed: {e}"

    async def screenshot_analyze_handler(args: str) -> str:
        path = args.strip()
        if not path:
            return "Usage: /screenshot-analyze <path_or_html_text>"
        try:
            from lidco.browser.screenshot_analyzer import ScreenshotAnalyzer
            from pathlib import Path as P
            analyzer = ScreenshotAnalyzer()
            if P(path).exists():
                result = analyzer.analyze_file(path)
            else:
                # Treat as HTML text
                result = analyzer.analyze_html_text(path)
            return result.format()
        except Exception as e:
            return f"/screenshot-analyze failed: {e}"

    from lidco.cli.commands.registry import SlashCommand
    registry.register(SlashCommand("browser", "Browser automation (navigate, screenshot)", browser_handler))
    registry.register(SlashCommand("visual-test", "Visual regression test runner", visual_test_handler))
    registry.register(SlashCommand("plan-act", "Plan/Act mode controller (Cline-style)", plan_act_handler))
    registry.register(SlashCommand("screenshot-analyze", "Analyze screenshot or HTML for visual issues", screenshot_analyze_handler))
