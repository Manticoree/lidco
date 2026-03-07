"""Git diff viewer — renders a syntax-highlighted panel after agent file changes."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

# Maximum number of diff lines to display before truncating.
_MAX_DIFF_LINES = 80


def get_git_diff(project_dir: Path | None = None) -> str:
    """Return ``git diff --unified=3`` output for *project_dir*.

    Returns an empty string when git is unavailable, times out, or there are
    no unstaged changes.
    """
    cwd = project_dir or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "diff", "--unified=3"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""


def show_git_diff(console: Console, project_dir: Path | None = None) -> None:
    """Run ``git diff`` and render a syntax-highlighted panel to *console*.

    Does nothing when there are no changes or git is unavailable.  Long diffs
    are truncated to :data:`_MAX_DIFF_LINES` lines with a count of hidden lines
    shown in the panel title.
    """
    diff_text = get_git_diff(project_dir).strip()
    if not diff_text:
        return

    lines = diff_text.splitlines()
    truncated = len(lines) > _MAX_DIFF_LINES
    shown_lines = lines[:_MAX_DIFF_LINES] if truncated else lines
    shown_text = "\n".join(shown_lines)

    syntax = Syntax(shown_text, "diff", theme="monokai", word_wrap=False)

    if truncated:
        hidden = len(lines) - _MAX_DIFF_LINES
        title = f"Changes  [{_MAX_DIFF_LINES} of {len(lines)} lines — {hidden} hidden]"
    else:
        title = "Changes"

    console.print(Panel(syntax, title=title, border_style="dim yellow"))
