"""Browser automation integration via Playwright CLI — Task 409."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


_PLAYWRIGHT_NOT_INSTALLED_MSG = (
    "Playwright is not installed. Install it with:\n"
    "  pip install playwright\n"
    "  playwright install chromium"
)


def _playwright_available() -> bool:
    """Return True if the playwright CLI is available on PATH."""
    return shutil.which("playwright") is not None


@dataclass
class BrowserSession:
    """Encapsulates a series of browser automation actions via the Playwright CLI.

    Actions are queued and executed via ``playwright codegen``-like subprocess
    calls.  This is a thin wrapper — it does not maintain a live browser
    process between calls.

    Args:
        browser: Browser type (chromium, firefox, webkit).  Defaults to chromium.
        timeout: Subprocess timeout in seconds.
    """

    browser: str = "chromium"
    timeout: int = 30
    _last_url: str = field(default="", init=False, repr=False)

    def navigate(self, url: str) -> str:
        """Navigate to a URL and return the page title (via playwright CLI).

        Args:
            url: Target URL.

        Returns:
            Status message.

        Raises:
            RuntimeError: If Playwright is not installed.
        """
        self._require_playwright()
        self._last_url = url
        # playwright open <url> exits immediately for scripted use;
        # we just verify the URL is reachable here via a short timeout.
        result = subprocess.run(
            ["playwright", "screenshot", "--browser", self.browser, url, "/dev/null"],
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            return f"Navigation to {url} may have failed: {stderr}"
        return f"Navigated to {url}"

    def screenshot(self, path: str, url: str | None = None) -> str:
        """Take a screenshot of the current or given URL.

        Args:
            path: Output file path for the screenshot.
            url: URL to screenshot (uses last navigated URL if omitted).

        Returns:
            Path to the saved screenshot.

        Raises:
            RuntimeError: If Playwright is not installed.
            ValueError: If no URL is available.
        """
        self._require_playwright()
        target_url = url or self._last_url
        if not target_url:
            raise ValueError("No URL provided and no previous navigation.")

        result = subprocess.run(
            ["playwright", "screenshot", "--browser", self.browser, target_url, path],
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"Screenshot failed: {stderr}")

        self._last_url = target_url
        return path

    def get_text(self, selector: str, url: str | None = None) -> str:
        """Extract text content of a selector from a URL.

        Uses ``playwright`` CLI with a script to get text content.

        Args:
            selector: CSS selector.
            url: URL to load (uses last navigated URL if omitted).

        Returns:
            Text content of the matched element, or an error message.

        Raises:
            RuntimeError: If Playwright is not installed.
            ValueError: If no URL is available.
        """
        self._require_playwright()
        target_url = url or self._last_url
        if not target_url:
            raise ValueError("No URL provided and no previous navigation.")

        script = (
            f"const {{ chromium }} = require('playwright');\n"
            f"(async () => {{\n"
            f"  const browser = await chromium.launch();\n"
            f"  const page = await browser.newPage();\n"
            f"  await page.goto('{target_url}');\n"
            f"  const text = await page.textContent('{selector}');\n"
            f"  console.log(text);\n"
            f"  await browser.close();\n"
            f"}})();"
        )
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            return f"Could not extract text: {result.stderr.strip()}"
        return result.stdout.strip()

    def click(self, selector: str, url: str | None = None) -> str:
        """Simulate a click on a selector.

        Args:
            selector: CSS selector to click.
            url: URL to load first (uses last navigated URL if omitted).

        Returns:
            Status message.

        Raises:
            RuntimeError: If Playwright is not installed.
        """
        self._require_playwright()
        target_url = url or self._last_url
        script = (
            f"const {{ chromium }} = require('playwright');\n"
            f"(async () => {{\n"
            f"  const browser = await chromium.launch();\n"
            f"  const page = await browser.newPage();\n"
            f"  await page.goto('{target_url}');\n"
            f"  await page.click('{selector}');\n"
            f"  console.log('clicked');\n"
            f"  await browser.close();\n"
            f"}})();"
        )
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            return f"Click may have failed: {result.stderr.strip()}"
        return f"Clicked selector '{selector}'"

    def fill(self, selector: str, text: str, url: str | None = None) -> str:
        """Fill a form field with text.

        Args:
            selector: CSS selector of the input.
            text: Text to fill.
            url: URL to load first (uses last navigated URL if omitted).

        Returns:
            Status message.

        Raises:
            RuntimeError: If Playwright is not installed.
        """
        self._require_playwright()
        target_url = url or self._last_url
        script = (
            f"const {{ chromium }} = require('playwright');\n"
            f"(async () => {{\n"
            f"  const browser = await chromium.launch();\n"
            f"  const page = await browser.newPage();\n"
            f"  await page.goto('{target_url}');\n"
            f"  await page.fill('{selector}', '{text}');\n"
            f"  console.log('filled');\n"
            f"  await browser.close();\n"
            f"}})();"
        )
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            return f"Fill may have failed: {result.stderr.strip()}"
        return f"Filled '{selector}' with text"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require_playwright() -> None:
        if not _playwright_available():
            raise RuntimeError(_PLAYWRIGHT_NOT_INSTALLED_MSG)


class BrowserTool(BaseTool):
    """Tool wrapper for browser automation via Playwright CLI.

    Registered as ``browser_action`` with ASK permission.
    """

    @property
    def name(self) -> str:
        return "browser_action"

    @property
    def description(self) -> str:
        return (
            "Automate browser actions via Playwright. "
            "Supports navigate, screenshot, click, fill, and get_text. "
            "Requires playwright to be installed."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform: navigate | screenshot | click | fill | get_text",
                enum=["navigate", "screenshot", "click", "fill", "get_text"],
            ),
            ToolParameter(
                name="url",
                type="string",
                description="URL to navigate to (required for navigate/screenshot).",
                required=False,
            ),
            ToolParameter(
                name="selector",
                type="string",
                description="CSS selector (required for click/fill/get_text).",
                required=False,
            ),
            ToolParameter(
                name="text",
                type="string",
                description="Text to fill (required for fill action).",
                required=False,
            ),
            ToolParameter(
                name="output_path",
                type="string",
                description="Output file path for screenshot action.",
                required=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(
        self,
        action: str = "navigate",
        url: str = "",
        selector: str = "",
        text: str = "",
        output_path: str = "",
        **_: Any,
    ) -> ToolResult:
        if not _playwright_available():
            return ToolResult(
                output="",
                success=False,
                error=_PLAYWRIGHT_NOT_INSTALLED_MSG,
            )

        session = BrowserSession()

        try:
            if action == "navigate":
                if not url:
                    return ToolResult(output="", success=False, error="url is required for navigate action")
                msg = session.navigate(url)
                return ToolResult(output=msg, success=True)

            elif action == "screenshot":
                if not url and not output_path:
                    return ToolResult(output="", success=False, error="url and output_path are required for screenshot")
                if not output_path:
                    output_path = "screenshot.png"
                saved = session.screenshot(output_path, url=url or None)
                return ToolResult(output=f"Screenshot saved to: {saved}", success=True)

            elif action == "click":
                if not selector:
                    return ToolResult(output="", success=False, error="selector is required for click action")
                if url:
                    session._last_url = url
                msg = session.click(selector)
                return ToolResult(output=msg, success=True)

            elif action == "fill":
                if not selector:
                    return ToolResult(output="", success=False, error="selector is required for fill action")
                if url:
                    session._last_url = url
                msg = session.fill(selector, text)
                return ToolResult(output=msg, success=True)

            elif action == "get_text":
                if not selector:
                    return ToolResult(output="", success=False, error="selector is required for get_text action")
                if url:
                    session._last_url = url
                content = session.get_text(selector)
                return ToolResult(output=content, success=True)

            else:
                return ToolResult(
                    output="",
                    success=False,
                    error=f"Unknown action: {action}. Valid: navigate, screenshot, click, fill, get_text",
                )
        except (RuntimeError, ValueError) as exc:
            return ToolResult(output="", success=False, error=str(exc))
