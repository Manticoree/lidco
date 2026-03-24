"""Tests for ModeController — T501."""
from __future__ import annotations
import pytest
from lidco.cli.mode import InteractionMode, ModeController


class TestModeController:
    def test_default_agent_mode(self):
        ctrl = ModeController()
        assert ctrl.current_mode == InteractionMode.AGENT

    def test_set_chat_mode(self):
        ctrl = ModeController()
        ctrl.set_mode(InteractionMode.CHAT)
        assert ctrl.is_chat
        assert not ctrl.is_agent

    def test_set_agent_mode(self):
        ctrl = ModeController(InteractionMode.CHAT)
        ctrl.set_mode(InteractionMode.AGENT)
        assert ctrl.is_agent

    def test_set_mode_from_string(self):
        ctrl = ModeController()
        ctrl.set_mode("chat")
        assert ctrl.current_mode == InteractionMode.CHAT

    def test_toggle_agent_to_chat(self):
        ctrl = ModeController(InteractionMode.AGENT)
        result = ctrl.toggle()
        assert result == InteractionMode.CHAT

    def test_toggle_chat_to_agent(self):
        ctrl = ModeController(InteractionMode.CHAT)
        result = ctrl.toggle()
        assert result == InteractionMode.AGENT

    def test_display_name_chat(self):
        ctrl = ModeController(InteractionMode.CHAT)
        assert "CHAT" in ctrl.display_name()

    def test_display_name_agent(self):
        ctrl = ModeController(InteractionMode.AGENT)
        assert "AGENT" in ctrl.display_name()

    def test_invalid_mode_string_raises(self):
        ctrl = ModeController()
        with pytest.raises(ValueError):
            ctrl.set_mode("invalid")
