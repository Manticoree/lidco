"""Vim Mode engine — modal editing for LIDCO REPL."""
from __future__ import annotations

import enum
from dataclasses import dataclass


class VimMode(enum.Enum):
    """Vim editing modes."""

    NORMAL = "normal"
    INSERT = "insert"
    VISUAL = "visual"
    COMMAND = "command"


@dataclass(frozen=True)
class VimState:
    """Immutable snapshot of the Vim engine state."""

    mode: VimMode
    cursor_pos: int
    register: str
    count: int


@dataclass(frozen=True)
class VimAction:
    """An action produced by the Vim engine after processing a key."""

    action_type: str  # MOVE, DELETE, YANK, PASTE, CHANGE_MODE, SEARCH, COMMAND
    params: dict[str, object]


_MODE_SWITCH_KEYS: dict[str, VimMode] = {
    "i": VimMode.INSERT,
    "v": VimMode.VISUAL,
    ":": VimMode.COMMAND,
}

_MOVEMENT_KEYS: dict[str, int] = {
    "h": -1,
    "l": 1,
    "j": 1,
    "k": -1,
}


class VimEngine:
    """Stateful Vim key processor.

    Returns *VimAction* for each keypress and keeps an immutable
    *VimState* snapshot accessible via :pyattr:`state`.
    """

    def __init__(self, initial_mode: VimMode = VimMode.NORMAL) -> None:
        self._mode = initial_mode
        self._cursor_pos = 0
        self._register = ""
        self._count = 0
        self._search_buffer = ""

    # -- public properties ------------------------------------------------

    @property
    def state(self) -> VimState:
        return VimState(
            mode=self._mode,
            cursor_pos=self._cursor_pos,
            register=self._register,
            count=self._count,
        )

    @property
    def mode(self) -> VimMode:
        return self._mode

    # -- mode switching ---------------------------------------------------

    def switch_mode(self, mode: VimMode) -> "VimEngine":
        """Return a **new** VimEngine set to *mode* (immutable style)."""
        new = VimEngine(initial_mode=mode)
        new._cursor_pos = self._cursor_pos
        new._register = self._register
        new._count = 0
        return new

    # -- key processing ---------------------------------------------------

    def process_key(self, key: str) -> VimAction:
        """Process a single *key* and return the resulting action."""
        if self._mode == VimMode.INSERT:
            return self._process_insert(key)
        if self._mode == VimMode.VISUAL:
            return self._process_visual(key)
        if self._mode == VimMode.COMMAND:
            return self._process_command(key)
        return self._process_normal(key)

    # -- private handlers -------------------------------------------------

    def _process_normal(self, key: str) -> VimAction:
        # Count prefix
        if key.isdigit() and (self._count > 0 or key != "0"):
            self._count = self._count * 10 + int(key)
            return VimAction(action_type="MOVE", params={"pending_count": self._count})

        count = max(self._count, 1)
        self._count = 0

        if key in _MODE_SWITCH_KEYS:
            self._mode = _MODE_SWITCH_KEYS[key]
            return VimAction(
                action_type="CHANGE_MODE",
                params={"mode": self._mode.value},
            )

        if key == "Escape":
            return VimAction(action_type="CHANGE_MODE", params={"mode": "normal"})

        if key in _MOVEMENT_KEYS:
            delta = _MOVEMENT_KEYS[key] * count
            self._cursor_pos = max(0, self._cursor_pos + delta)
            return VimAction(action_type="MOVE", params={"delta": delta, "cursor": self._cursor_pos})

        if key == "x":
            return VimAction(action_type="DELETE", params={"count": count, "cursor": self._cursor_pos})

        if key == "y":
            return VimAction(action_type="YANK", params={"count": count, "cursor": self._cursor_pos})

        if key == "p":
            return VimAction(action_type="PASTE", params={"register": self._register, "cursor": self._cursor_pos})

        if key == "d":
            return VimAction(action_type="DELETE", params={"count": count, "cursor": self._cursor_pos})

        if key == "/":
            self._search_buffer = ""
            return VimAction(action_type="SEARCH", params={"start": True})

        if key == "0":
            self._cursor_pos = 0
            return VimAction(action_type="MOVE", params={"delta": 0, "cursor": 0})

        if key == "$":
            return VimAction(action_type="MOVE", params={"end_of_line": True, "cursor": self._cursor_pos})

        return VimAction(action_type="COMMAND", params={"key": key})

    def _process_insert(self, key: str) -> VimAction:
        if key == "Escape":
            self._mode = VimMode.NORMAL
            return VimAction(action_type="CHANGE_MODE", params={"mode": "normal"})
        # In insert mode every key is a character insertion
        self._cursor_pos += 1
        return VimAction(action_type="COMMAND", params={"char": key, "cursor": self._cursor_pos})

    def _process_visual(self, key: str) -> VimAction:
        if key == "Escape":
            self._mode = VimMode.NORMAL
            return VimAction(action_type="CHANGE_MODE", params={"mode": "normal"})
        if key in _MOVEMENT_KEYS:
            self._cursor_pos = max(0, self._cursor_pos + _MOVEMENT_KEYS[key])
            return VimAction(action_type="MOVE", params={"delta": _MOVEMENT_KEYS[key], "cursor": self._cursor_pos})
        if key == "y":
            self._mode = VimMode.NORMAL
            return VimAction(action_type="YANK", params={"cursor": self._cursor_pos})
        if key == "d":
            self._mode = VimMode.NORMAL
            return VimAction(action_type="DELETE", params={"cursor": self._cursor_pos})
        return VimAction(action_type="COMMAND", params={"key": key})

    def _process_command(self, key: str) -> VimAction:
        if key == "Escape":
            self._mode = VimMode.NORMAL
            return VimAction(action_type="CHANGE_MODE", params={"mode": "normal"})
        if key == "\n" or key == "Enter":
            self._mode = VimMode.NORMAL
            return VimAction(action_type="COMMAND", params={"execute": True})
        return VimAction(action_type="COMMAND", params={"char": key})
