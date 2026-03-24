"""InteractionMode — chat vs. agent mode distinction."""
from __future__ import annotations

from enum import Enum


class InteractionMode(str, Enum):
    CHAT = "chat"      # Direct LLM, no tools, no pipeline — fast
    AGENT = "agent"    # Full graph orchestration with tools


class ModeController:
    """Manage current interaction mode."""

    def __init__(self, mode: InteractionMode = InteractionMode.AGENT) -> None:
        self._mode = mode

    @property
    def current_mode(self) -> InteractionMode:
        return self._mode

    @property
    def is_chat(self) -> bool:
        return self._mode == InteractionMode.CHAT

    @property
    def is_agent(self) -> bool:
        return self._mode == InteractionMode.AGENT

    def set_mode(self, mode: InteractionMode | str) -> None:
        if isinstance(mode, str):
            mode = InteractionMode(mode.lower())
        self._mode = mode

    def toggle(self) -> InteractionMode:
        """Toggle between CHAT and AGENT."""
        if self._mode == InteractionMode.CHAT:
            self._mode = InteractionMode.AGENT
        else:
            self._mode = InteractionMode.CHAT
        return self._mode

    def display_name(self) -> str:
        return f"[{self._mode.value.upper()}]"
