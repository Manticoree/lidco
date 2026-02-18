"""Permission system for tool execution."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from rich.console import Console

from lidco.core.config import PermissionsConfig
from lidco.tools.base import ToolPermission


@dataclass(frozen=True)
class _Choice:
    label: str
    description: str
    key: str


_CHOICES: tuple[_Choice, ...] = (
    _Choice(label="Allow once", description="Allow this single operation", key="y"),
    _Choice(
        label="Allow this tool for session",
        description="Auto-allow all future uses of this tool",
        key="t",
    ),
    _Choice(
        label="Allow all for session",
        description="Auto-allow every tool for the rest of this session",
        key="a",
    ),
    _Choice(label="Deny", description="Block this operation", key="n"),
)


def _run_permission_prompt(tool_name: str, params: dict, console: Console) -> str:
    """Show a Claude Code-style arrow-key selector. Returns choice key."""
    selected = [0]

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _up(event) -> None:  # type: ignore[no-untyped-def]
        selected[0] = (selected[0] - 1) % len(_CHOICES)

    @kb.add("down")
    @kb.add("j")
    def _down(event) -> None:  # type: ignore[no-untyped-def]
        selected[0] = (selected[0] + 1) % len(_CHOICES)

    @kb.add("enter")
    def _accept(event) -> None:  # type: ignore[no-untyped-def]
        event.app.exit(result=_CHOICES[selected[0]].key)

    # Shortcut keys
    for idx, choice in enumerate(_CHOICES):

        def _make_handler(key: str):  # type: ignore[no-untyped-def]
            def _handler(event) -> None:  # type: ignore[no-untyped-def]
                event.app.exit(result=key)

            return _handler

        kb.add(choice.key)(_make_handler(choice.key))

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event) -> None:  # type: ignore[no-untyped-def]
        event.app.exit(result="n")

    # Render param summary
    param_lines: list[str] = []
    for k, v in params.items():
        display = str(v)[:200]
        param_lines.append(f"  {k}: {display}")
    param_block = "\n".join(param_lines)

    def _get_text() -> FormattedText:
        fragments: list[tuple[str, str]] = []
        fragments.append(("class:header", f"  {tool_name}"))
        fragments.append(("", " wants to execute:\n"))
        for line in param_lines:
            fragments.append(("class:param", f"{line}\n"))
        fragments.append(("", "\n"))
        for i, choice in enumerate(_CHOICES):
            if i == selected[0]:
                fragments.append(("class:pointer", "  > "))
                fragments.append(("class:selected", f"{choice.label}"))
                fragments.append(("class:desc", f"  {choice.description}"))
            else:
                fragments.append(("", "    "))
                fragments.append(("class:option", f"{choice.label}"))
                fragments.append(("class:desc-dim", f"  {choice.description}"))
            fragments.append(("", "\n"))
        fragments.append(("class:hint", "\n  Use arrows to move, Enter to confirm, or press shortcut key\n"))
        return FormattedText(fragments)

    control = FormattedTextControl(_get_text)
    window = Window(content=control, always_hide_cursor=True)

    style_dict = {
        "header": "bold yellow",
        "param": "gray",
        "pointer": "bold magenta",
        "selected": "bold white",
        "desc": "italic",
        "option": "",
        "desc-dim": "gray italic",
        "hint": "gray",
    }

    from prompt_toolkit.styles import Style

    style = Style.from_dict(style_dict)

    app: Application[str] = Application(
        layout=Layout(window),
        key_bindings=kb,
        style=style,
        full_screen=False,
    )

    return app.run()


class PermissionManager:
    """Manages tool execution permissions."""

    def __init__(self, config: PermissionsConfig, console: Console | None = None) -> None:
        self._config = config
        self._console = console or Console()
        self._session_allowed: set[str] = set()
        self._allow_all: bool = False

    def check(self, tool_name: str, params: dict) -> bool:
        """Check if a tool execution is allowed.

        Returns True if allowed, False if denied.
        """
        level = self._config.get_level(tool_name)

        if level == ToolPermission.DENY:
            self._console.print(f"[red]Tool '{tool_name}' is denied by configuration.[/red]")
            return False

        if level == ToolPermission.AUTO:
            return True

        if self._allow_all or tool_name in self._session_allowed:
            return True

        choice = _run_permission_prompt(tool_name, params, self._console)

        if choice == "n":
            self._console.print("[red]Denied.[/red]")
            return False

        if choice == "a":
            self._allow_all = True
            self._console.print("[green]All tools auto-allowed for this session.[/green]")
            return True

        if choice == "t":
            self._session_allowed.add(tool_name)
            self._console.print(f"[green]'{tool_name}' auto-allowed for this session.[/green]")

        return True

    def auto_allow(self, tool_name: str) -> None:
        """Mark a tool as auto-allowed for this session."""
        self._session_allowed.add(tool_name)

    def allow_all(self) -> None:
        """Auto-allow all tools for this session."""
        self._allow_all = True
