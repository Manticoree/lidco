"""ChatModeManager — manage chat modes (code, ask, architect, help) (stdlib only)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ChatMode(Enum):
    CODE = "code"
    ASK = "ask"
    ARCHITECT = "architect"
    HELP = "help"


_EDIT_MODES = {ChatMode.CODE, ChatMode.ARCHITECT}


@dataclass
class ModeTransition:
    from_mode: ChatMode
    to_mode: ChatMode
    timestamp: str
    warning: Optional[str] = None


class ChatModeManager:
    """Manage active chat mode with transition history."""

    def __init__(self, session=None) -> None:
        self._session = session
        self._mode = ChatMode.CODE
        self._history: list[ModeTransition] = []

    @property
    def active_mode(self) -> ChatMode:
        return self._mode

    def switch(self, mode: str | ChatMode) -> ModeTransition:
        """Switch to a new mode. Returns ModeTransition."""
        if isinstance(mode, ChatMode):
            new_mode = mode
        else:
            cleaned = mode.strip().lower()
            try:
                new_mode = ChatMode(cleaned)
            except ValueError:
                raise ValueError(f"Invalid mode: {mode!r}. Choose from: {', '.join(m.value for m in ChatMode)}")

        warning: str | None = None
        if new_mode == ChatMode.ASK and self._session is not None:
            plan = getattr(self._session, "current_plan", None)
            if plan is not None:
                applied = getattr(self._session, "_applied", True)
                if not applied:
                    warning = "Switching to ASK mode with pending edits — edits will not be applied."

        transition = ModeTransition(
            from_mode=self._mode,
            to_mode=new_mode,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            warning=warning,
        )
        self._mode = new_mode
        self._history = [*self._history, transition]
        return transition

    def history(self) -> list[ModeTransition]:
        return list(self._history)

    def is_edit_allowed(self) -> bool:
        """Returns False in ASK and HELP modes."""
        return self._mode in _EDIT_MODES

    def reset(self) -> None:
        """Reset to CODE mode."""
        self._mode = ChatMode.CODE
