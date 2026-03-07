"""Post-edit linting integration for the CLI.

Runs ruff on Python files that were just modified by the agent and renders
the results as a compact Rich panel.  Missing ruff installation is handled
gracefully (no crash, no output).
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

logger = logging.getLogger(__name__)

_MAX_LINT_LINES = 40


def _run_ruff(paths: list[str]) -> str:
    """Run ``ruff check`` on *paths* and return its stdout, or '' on error."""
    try:
        result = subprocess.run(
            [
                "ruff", "check",
                "--select=E,F,W",
                "--output-format=concise",
                "--no-cache",
                *paths,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        # ruff not installed — silently skip
        return ""
    except subprocess.TimeoutExpired:
        logger.debug("ruff timed out after 15 s")
        return ""
    except OSError as e:
        logger.debug("ruff error: %s", e)
        return ""


def show_lint_results(console: Console, paths: list[str]) -> None:
    """Run ruff on *paths* and print a panel if there are issues.

    Only Python files are linted.  The function is a no-op when ruff is
    not installed or when all files pass cleanly.
    """
    py_paths = [p for p in paths if Path(p).suffix == ".py"]
    if not py_paths:
        return

    output = _run_ruff(py_paths)
    if not output:
        return

    lines = output.splitlines()
    truncated = len(lines) > _MAX_LINT_LINES
    shown_text = "\n".join(lines[:_MAX_LINT_LINES])
    if truncated:
        shown_text += f"\n... ({len(lines) - _MAX_LINT_LINES} more issues)"

    issue_word = "issue" if len(lines) == 1 else "issues"
    title = f"Lint  {len(lines)} {issue_word}"

    syntax = Syntax(shown_text, "text", theme="monokai", word_wrap=True)
    console.print(Panel(syntax, title=title, border_style="dim red"))
