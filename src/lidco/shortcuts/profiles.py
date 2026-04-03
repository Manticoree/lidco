"""Shortcut profiles — preset and custom, switch and merge."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.shortcuts.registry import Shortcut, ShortcutRegistry


@dataclass
class Profile:
    """A named collection of shortcuts."""

    name: str
    shortcuts: list[Shortcut] = field(default_factory=list)
    description: str = ""


# ------------------------------------------------------------------ #
# built-in profiles
# ------------------------------------------------------------------ #

def _default_shortcuts() -> list[Shortcut]:
    return [
        Shortcut("ctrl+s", "save", "Save file"),
        Shortcut("ctrl+z", "undo", "Undo"),
        Shortcut("ctrl+y", "redo", "Redo"),
        Shortcut("ctrl+c", "copy", "Copy selection"),
        Shortcut("ctrl+v", "paste", "Paste"),
        Shortcut("ctrl+x", "cut", "Cut selection"),
        Shortcut("ctrl+f", "find", "Find"),
        Shortcut("ctrl+h", "replace", "Replace"),
        Shortcut("ctrl+p", "palette", "Command palette"),
        Shortcut("ctrl+q", "quit", "Quit"),
    ]


def _vim_shortcuts() -> list[Shortcut]:
    return [
        Shortcut("i", "insert_mode", "Enter insert mode"),
        Shortcut("escape", "normal_mode", "Enter normal mode"),
        Shortcut("dd", "delete_line", "Delete line"),
        Shortcut("yy", "yank_line", "Yank line"),
        Shortcut("p", "paste_after", "Paste after cursor"),
        Shortcut("u", "undo", "Undo"),
        Shortcut("ctrl+r", "redo", "Redo"),
        Shortcut("/", "search", "Search"),
        Shortcut(":w", "save", "Save file"),
        Shortcut(":q", "quit", "Quit"),
    ]


def _emacs_shortcuts() -> list[Shortcut]:
    return [
        Shortcut("ctrl+x ctrl+s", "save", "Save file"),
        Shortcut("ctrl+x ctrl+c", "quit", "Quit"),
        Shortcut("ctrl+g", "cancel", "Cancel"),
        Shortcut("ctrl+s", "search", "Incremental search"),
        Shortcut("ctrl+w", "cut", "Cut region"),
        Shortcut("alt+w", "copy", "Copy region"),
        Shortcut("ctrl+y", "paste", "Yank (paste)"),
        Shortcut("ctrl+/", "undo", "Undo"),
        Shortcut("ctrl+x ctrl+f", "find_file", "Open file"),
        Shortcut("alt+x", "palette", "Execute command"),
    ]


def _vscode_shortcuts() -> list[Shortcut]:
    return [
        Shortcut("ctrl+shift+p", "palette", "Command palette"),
        Shortcut("ctrl+p", "quick_open", "Quick open file"),
        Shortcut("ctrl+shift+f", "search_all", "Search in files"),
        Shortcut("ctrl+b", "toggle_sidebar", "Toggle sidebar"),
        Shortcut("ctrl+`", "toggle_terminal", "Toggle terminal"),
        Shortcut("ctrl+s", "save", "Save file"),
        Shortcut("ctrl+z", "undo", "Undo"),
        Shortcut("ctrl+shift+z", "redo", "Redo"),
        Shortcut("ctrl+d", "select_next", "Select next match"),
        Shortcut("ctrl+shift+k", "delete_line", "Delete line"),
    ]


_BUILTINS: dict[str, tuple[list[Shortcut], str]] = {
    "default": (_default_shortcuts, "Default keyboard shortcuts"),  # type: ignore[dict-item]
    "vim": (_vim_shortcuts, "Vim-style shortcuts"),  # type: ignore[dict-item]
    "emacs": (_emacs_shortcuts, "Emacs-style shortcuts"),  # type: ignore[dict-item]
    "vscode": (_vscode_shortcuts, "VS Code-style shortcuts"),  # type: ignore[dict-item]
}


class ShortcutProfiles:
    """Manage shortcut profiles; activate; merge."""

    def __init__(self, registry: ShortcutRegistry) -> None:
        self._registry = registry
        self._profiles: dict[str, Profile] = {}
        self._active: str = "default"

        # create built-in profiles
        for name, (factory, desc) in _BUILTINS.items():
            self._profiles[name] = Profile(name=name, shortcuts=factory(), description=desc)

        # activate default
        self.activate("default")

    # ------------------------------------------------------------------

    def create(self, name: str, shortcuts: list[Shortcut] | None = None, description: str = "") -> Profile:
        profile = Profile(name=name, shortcuts=list(shortcuts or []), description=description)
        self._profiles[name] = profile
        return profile

    def get(self, name: str) -> Profile | None:
        return self._profiles.get(name)

    def activate(self, name: str) -> bool:
        profile = self._profiles.get(name)
        if profile is None:
            return False
        # clear registry and load profile shortcuts
        self._registry._shortcuts.clear()
        for s in profile.shortcuts:
            try:
                self._registry.register(s)
            except ValueError:
                pass  # skip duplicates within same profile
        self._active = name
        return True

    def active(self) -> str:
        return self._active

    def merge(self, base: str, overlay: str, new_name: str) -> Profile:
        base_p = self._profiles.get(base)
        overlay_p = self._profiles.get(overlay)
        if base_p is None:
            raise ValueError(f"Profile '{base}' not found")
        if overlay_p is None:
            raise ValueError(f"Profile '{overlay}' not found")
        # base shortcuts, then overlay overrides by keys+context
        merged: dict[tuple[str, str], Shortcut] = {}
        for s in base_p.shortcuts:
            merged[(s.keys.lower(), s.context)] = s
        for s in overlay_p.shortcuts:
            merged[(s.keys.lower(), s.context)] = s
        profile = Profile(
            name=new_name,
            shortcuts=list(merged.values()),
            description=f"Merge of {base} + {overlay}",
        )
        self._profiles[new_name] = profile
        return profile

    def all_profiles(self) -> list[Profile]:
        return list(self._profiles.values())

    def builtin_names(self) -> list[str]:
        return list(_BUILTINS.keys())

    def summary(self) -> dict:
        return {
            "active": self._active,
            "total": len(self._profiles),
            "builtin": list(_BUILTINS.keys()),
            "custom": [n for n in self._profiles if n not in _BUILTINS],
        }
