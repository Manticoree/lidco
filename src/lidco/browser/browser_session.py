"""Playwright-based browser automation for visual debugging and E2E testing (Cline parity)."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from playwright.async_api import async_playwright, Page, Browser
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None  # type: ignore[assignment]
    Page = None              # type: ignore[assignment]
    Browser = None           # type: ignore[assignment]
    _PLAYWRIGHT_AVAILABLE = False


@dataclass
class BrowserAction:
    kind: str          # "navigate" | "click" | "fill" | "screenshot" | "evaluate"
    selector: str = ""
    value: str = ""
    url: str = ""


@dataclass
class BrowserResult:
    action: BrowserAction
    success: bool
    output: str = ""       # text result or base64 screenshot
    error: str = ""
    screenshot_b64: str = ""  # base64 PNG if action was screenshot


@dataclass
class SessionSummary:
    actions_taken: int
    screenshots: int
    errors: int
    final_url: str = ""


class BrowserSession:
    """Manage a browser session for autonomous visual testing and debugging.

    Falls back gracefully when Playwright is not installed.
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 10_000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._history: list[BrowserResult] = []
        self._available = _PLAYWRIGHT_AVAILABLE

    @property
    def is_available(self) -> bool:
        return self._available

    async def run_actions(self, actions: list[BrowserAction]) -> list[BrowserResult]:
        """Execute a list of browser actions sequentially."""
        if not self._available:
            return [BrowserResult(action=a, success=False, error="Playwright not installed") for a in actions]

        results: list[BrowserResult] = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            page.set_default_timeout(self.timeout_ms)

            for action in actions:
                result = await self._execute(page, action)
                results.append(result)
                self._history.append(result)
                if not result.success:
                    break  # stop on first failure

            await browser.close()
        return results

    async def _execute(self, page: Any, action: BrowserAction) -> BrowserResult:
        try:
            if action.kind == "navigate":
                await page.goto(action.url or action.value)
                return BrowserResult(action=action, success=True, output=f"Navigated to {action.url or action.value}")
            elif action.kind == "click":
                await page.click(action.selector)
                return BrowserResult(action=action, success=True, output=f"Clicked {action.selector}")
            elif action.kind == "fill":
                await page.fill(action.selector, action.value)
                return BrowserResult(action=action, success=True, output=f"Filled {action.selector}")
            elif action.kind == "screenshot":
                data = await page.screenshot()
                b64 = base64.b64encode(data).decode()
                return BrowserResult(action=action, success=True, output="Screenshot captured", screenshot_b64=b64)
            elif action.kind == "evaluate":
                result = await page.evaluate(action.value)
                return BrowserResult(action=action, success=True, output=str(result))
            else:
                return BrowserResult(action=action, success=False, error=f"Unknown action: {action.kind}")
        except Exception as e:
            return BrowserResult(action=action, success=False, error=str(e))

    def get_history(self) -> list[BrowserResult]:
        return list(self._history)

    def summary(self) -> SessionSummary:
        screenshots = sum(1 for r in self._history if r.action.kind == "screenshot" and r.success)
        errors = sum(1 for r in self._history if not r.success)
        final_url = ""
        for r in reversed(self._history):
            if r.action.kind == "navigate" and r.success:
                final_url = r.action.url or r.action.value
                break
        return SessionSummary(
            actions_taken=len(self._history),
            screenshots=screenshots,
            errors=errors,
            final_url=final_url,
        )
