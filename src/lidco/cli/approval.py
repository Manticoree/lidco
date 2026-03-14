"""Interactive approval prompt for tool permission requests.

Replaces the 4-choice prompt in permissions.py with a richer 6-choice
prompt that supports persistent allow/deny rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from rich.console import Console

from lidco.core.permission_engine import PermissionResult


class Decision(str, Enum):
    ALLOW_ONCE = "allow_once"
    ALLOW_SESSION = "allow_session"
    ALLOW_ALWAYS = "allow_always"
    DENY_ONCE = "deny_once"
    DENY_ALWAYS = "deny_always"
    EXPLAIN = "explain"


@dataclass(frozen=True)
class _Choice:
    key: str
    label: str
    description: str
    decision: Decision


_CHOICES: tuple[_Choice, ...] = (
    _Choice("y", "Allow once",          "Allow this single operation",              Decision.ALLOW_ONCE),
    _Choice("s", "Allow for session",   "Auto-allow this tool for the rest of the session", Decision.ALLOW_SESSION),
    _Choice("a", "Always allow",        "Remember this permanently (.lidco/permissions.json)", Decision.ALLOW_ALWAYS),
    _Choice("n", "Deny once",           "Block this operation",                     Decision.DENY_ONCE),
    _Choice("N", "Never allow",         "Block permanently and remember",           Decision.DENY_ALWAYS),
    _Choice("e", "Explain",             "Show why permission is needed",            Decision.EXPLAIN),
)

_RISK_COLORS = {
    "green": "ansigreen",
    "yellow": "ansiyellow",
    "red": "ansired",
}

_STYLE = Style.from_dict({
    "header":    "bold",
    "risk-green": "ansigreen bold",
    "risk-yellow": "ansiyellow bold",
    "risk-red":  "ansired bold",
    "param-key": "ansiblue",
    "param-val": "gray",
    "pointer":   "bold ansimagenta",
    "selected":  "bold white",
    "desc":      "italic",
    "option":    "",
    "desc-dim":  "gray italic",
    "hint":      "gray",
    "key":       "bold ansicyan",
})

_TOOL_EXPLANATIONS: dict[str, str] = {
    "bash":       "Execute shell commands. Could modify files, run tests, or interact with the OS.",
    "file_write": "Create or overwrite a file on disk.",
    "file_edit":  "Modify an existing file (find-and-replace or patch).",
    "git":        "Run a git command. Some git ops (push, reset --hard) are irreversible.",
    "web_search": "Search the web. Results are read-only.",
    "web_fetch":  "Fetch a URL. Read-only.",
}


def ask(
    tool_name: str,
    args: dict[str, Any],
    result: PermissionResult,
    console: Console,
) -> Decision:
    """Show interactive approval prompt. Returns user's Decision."""
    while True:
        decision = _run_prompt(tool_name, args, result)
        if decision == Decision.EXPLAIN:
            explanation = _TOOL_EXPLANATIONS.get(
                tool_name.lower(),
                f"Runs the '{tool_name}' tool with the shown parameters.",
            )
            console.print(f"\n[dim]  {explanation}[/dim]\n")
            # Re-show prompt after explanation
            continue
        return decision


def _run_prompt(
    tool_name: str,
    args: dict[str, Any],
    result: PermissionResult,
) -> Decision:
    """Render and run the prompt_toolkit approval UI."""
    selected = [0]
    choices = _CHOICES

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _up(event) -> None:  # type: ignore[no-untyped-def]
        selected[0] = (selected[0] - 1) % len(choices)

    @kb.add("down")
    @kb.add("j")
    def _down(event) -> None:  # type: ignore[no-untyped-def]
        selected[0] = (selected[0] + 1) % len(choices)

    @kb.add("enter")
    def _accept(event) -> None:  # type: ignore[no-untyped-def]
        event.app.exit(result=choices[selected[0]].decision.value)

    for choice in choices:
        key = choice.key

        def _make_handler(k: str):  # type: ignore[no-untyped-def]
            def _handler(event) -> None:  # type: ignore[no-untyped-def]
                event.app.exit(result=Decision(k if k == "N" else k).value if k in ("N",) else
                               next(c.decision.value for c in choices if c.key == k))
            return _handler

        try:
            kb.add(key)(_make_handler(key))
        except Exception:
            pass  # skip duplicate key registration

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event) -> None:  # type: ignore[no-untyped-def]
        event.app.exit(result=Decision.DENY_ONCE.value)

    risk_style = f"class:risk-{result.risk}"

    # Build parameter lines (truncated)
    param_lines: list[tuple[str, str]] = []
    for k, v in args.items():
        display = str(v)
        if len(display) > 120:
            display = display[:117] + "..."
        param_lines.append((k, display))

    def _get_text() -> FormattedText:
        frags: list[tuple[str, str]] = []
        # Header
        frags.append((risk_style, f"  {tool_name}"))
        frags.append(("", " — permission required\n"))
        # Params
        for pk, pv in param_lines:
            frags.append(("class:param-key", f"  {pk}: "))
            frags.append(("class:param-val", f"{pv}\n"))
        frags.append(("", "\n"))
        # Choices
        for i, choice in enumerate(choices):
            if i == selected[0]:
                frags.append(("class:pointer", "  ❯ "))
                frags.append(("class:selected", f"[{choice.key}] {choice.label}"))
                frags.append(("class:desc", f"   {choice.description}"))
            else:
                frags.append(("", "    "))
                frags.append(("class:option", f"[{choice.key}] {choice.label}"))
                frags.append(("class:desc-dim", f"   {choice.description}"))
            frags.append(("", "\n"))
        frags.append(("class:hint", "\n  ↑↓ to move · Enter to confirm · shortcut key to jump\n"))
        return FormattedText(frags)

    control = FormattedTextControl(_get_text)
    window = Window(content=control, always_hide_cursor=True)
    app: Application[str] = Application(
        layout=Layout(window),
        key_bindings=kb,
        style=_STYLE,
        full_screen=False,
    )
    raw = app.run()
    return Decision(raw)
