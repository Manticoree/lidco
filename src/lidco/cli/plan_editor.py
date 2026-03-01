"""Interactive plan step editor — lets users approve/skip individual plan steps.

When the planner returns a numbered plan, this module:
1. Parses the numbered steps (``1. ...``, ``2. ...``, etc.)
2. Shows the full plan in a panel with each step highlighted
3. Prompts the user to enter which steps to include
4. Validates step dependencies (``Deps:`` fields) and warns on violations
5. Returns a filtered plan string (or None to reject entirely)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

# Matches lines that begin a numbered step:
#   "1. text", "1) text", "Step 1: text", "Step 1. text"
# Captures the text after the number/prefix.
_STEP_RE = re.compile(
    r"^\s*(?:step\s+)?\d+[.):\s]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

# Matches the leading step number for dep parsing.
_STEP_NUM_RE = re.compile(r"^\s*(?:step\s+)?(\d+)[.):\s]\s*.+", re.IGNORECASE)

# Matches "Deps: ..." continuation lines following a step.
_DEPS_LINE_RE = re.compile(r"^\s*deps:\s*(.+)$", re.IGNORECASE)


def parse_plan_steps(text: str) -> list[str]:
    """Return the step descriptions extracted from *text*.

    Only the step content is returned (e.g. ``"Set up authentication module"``),
    not the leading number.  Returns an empty list when no numbered steps are
    found.
    """
    return [m.group(1).strip() for m in _STEP_RE.finditer(text)]


def _extract_plan_header(text: str) -> str:
    """Return any introductory lines before the first numbered step."""
    match = _STEP_RE.search(text)
    if not match:
        return ""
    header = text[: match.start()].strip()
    return header


def _parse_step_deps(text: str) -> dict[int, list[int]]:
    """Parse ``Deps:`` continuation lines from each numbered step block.

    Returns a mapping ``{step_number: [dep_step_numbers]}``.  Steps that have
    ``Deps: none`` (or no ``Deps:`` line) map to an empty list.

    Parses the full text in order; later step entries overwrite earlier ones for
    the same number, so plan sections that appear before **Steps:** (e.g.
    Chain-of-Thought numbered items) are naturally overridden by the real steps.
    """
    lines = text.splitlines()
    deps: dict[int, list[int]] = {}
    current_step: int | None = None

    for line in lines:
        num_match = _STEP_NUM_RE.match(line)
        if num_match:
            current_step = int(num_match.group(1))
            deps.setdefault(current_step, [])
        elif current_step is not None:
            deps_match = _DEPS_LINE_RE.match(line)
            if deps_match:
                raw = deps_match.group(1).strip().lower()
                if raw in ("none", "–", "-", "n/a", "—"):
                    deps[current_step] = []
                else:
                    dep_nums: list[int] = []
                    for token in re.split(r"[,\s]+", raw):
                        token = token.strip()
                        if token.isdigit():
                            dep_nums.append(int(token))
                    deps[current_step] = dep_nums

    return deps


def _resolve_deps(selected: set[int], deps: dict[int, list[int]]) -> set[int]:
    """Expand *selected* with all required transitive dependencies.

    Iteratively adds missing dependencies until no new ones are found.
    """
    resolved = set(selected)
    changed = True
    while changed:
        changed = False
        for step_num in list(resolved):
            for dep in deps.get(step_num, []):
                if dep not in resolved:
                    resolved.add(dep)
                    changed = True
    return resolved


def edit_plan_interactively(plan_text: str, console: "Console") -> str | None:
    """Show the plan and let the user select which steps to include.

    Args:
        plan_text: Full plan text from the planner agent.
        console:   Rich Console for display and prompting.

    Returns:
        A (possibly filtered) plan string to use as context, or ``None`` if the
        user rejected the plan entirely.  When no numbered steps are found the
        user is asked to approve or reject the whole plan.
    """
    from rich.panel import Panel
    from rich.prompt import Prompt

    steps = parse_plan_steps(plan_text)

    if not steps:
        # No numbered steps — show full plan, ask approve/reject
        console.print(Panel(plan_text, title="Generated Plan", border_style="dim cyan"))
        console.print()
        answer = Prompt.ask(
            "Approve this plan? (yes/no)",
            default="yes",
        ).strip().lower()
        if answer in ("no", "n", "reject", "none", "0"):
            return None
        return plan_text

    # Show the full plan panel without truncation
    console.print(Panel(plan_text, title="Generated Plan", border_style="dim cyan"))
    console.print()

    # Show parsed steps
    console.print("[bold]Plan steps:[/bold]")
    for i, step in enumerate(steps, 1):
        console.print(f"  [cyan]{i}.[/cyan] {step}")
    console.print()

    answer = Prompt.ask(
        f"Steps to include [1–{len(steps)}] (e.g. 1,3 · 'all' · 'none')",
        default="all",
    ).strip().lower()

    if answer in ("none", "0", "reject", "no", "n"):
        return None

    if answer in ("all", "yes", "y", ""):
        return plan_text

    # Parse comma-separated step numbers
    try:
        selected_nums: set[int] = set()
        for token in answer.replace(";", ",").split(","):
            token = token.strip()
            if not token:
                continue
            # Support ranges like "1-3"
            if "-" in token:
                parts = token.split("-", 1)
                start, end = int(parts[0]), int(parts[1])
                if start > end:
                    start, end = end, start
                selected_nums.update(range(start, end + 1))
            else:
                selected_nums.add(int(token))
    except ValueError:
        # Can't parse — approve all to avoid data loss
        return plan_text

    # Check for dependency violations and optionally auto-resolve
    step_deps = _parse_step_deps(plan_text)
    violations = [
        (s, [d for d in step_deps.get(s, []) if d not in selected_nums])
        for s in sorted(selected_nums)
        if any(d not in selected_nums for d in step_deps.get(s, []))
    ]
    if violations:
        console.print()
        console.print("[yellow]⚠ Dependency warnings:[/yellow]")
        for step_num, missing in violations:
            missing_str = ", ".join(str(d) for d in missing)
            console.print(
                f"  Step {step_num} depends on step(s) {missing_str} which are not selected."
            )
        dep_answer = Prompt.ask(
            "Add missing dependencies automatically? (yes/no)",
            default="yes",
        ).strip().lower()
        if dep_answer in ("yes", "y", ""):
            resolved = _resolve_deps(selected_nums, step_deps)
            added = sorted(resolved - selected_nums)
            if added:
                added_str = ", ".join(str(d) for d in added)
                console.print(
                    f"[green]Adding step(s) {added_str} (required dependencies).[/green]"
                )
            selected_nums = resolved

    # Filter to valid indices
    selected_steps = [
        step for i, step in enumerate(steps, 1) if i in selected_nums
    ]
    if not selected_steps:
        return None

    # Rebuild: keep header + renumbered steps
    header = _extract_plan_header(plan_text)
    filtered_lines: list[str] = []
    if header:
        filtered_lines.append(header)
    for i, step in enumerate(selected_steps, 1):
        filtered_lines.append(f"{i}. {step}")
    return "\n".join(filtered_lines)
