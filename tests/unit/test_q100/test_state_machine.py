"""Tests for T634 StateMachine."""
import pytest

from lidco.core.state_machine import HistoryEntry, InvalidTransition, State, StateMachine, Transition


class TestStateMachine:
    def test_initial_state(self):
        sm = StateMachine("idle")
        assert sm.current_state == "idle"

    def test_add_transition_and_trigger(self):
        sm = StateMachine("idle")
        sm.add_transition("idle", "active", "start")
        new_state = sm.trigger("start")
        assert new_state == "active"
        assert sm.current_state == "active"

    def test_invalid_transition_raises(self):
        sm = StateMachine("idle")
        with pytest.raises(InvalidTransition):
            sm.trigger("stop")

    def test_invalid_transition_carries_info(self):
        sm = StateMachine("idle")
        try:
            sm.trigger("badtrigger")
        except InvalidTransition as exc:
            assert exc.state == "idle"
            assert exc.trigger == "badtrigger"

    def test_guard_blocks_transition(self):
        sm = StateMachine("idle")
        sm.add_transition("idle", "active", "start", guard=lambda: False)
        with pytest.raises(InvalidTransition):
            sm.trigger("start")

    def test_guard_allows_transition(self):
        sm = StateMachine("idle")
        sm.add_transition("idle", "active", "start", guard=lambda: True)
        assert sm.trigger("start") == "active"

    def test_action_called_on_transition(self):
        calls = []
        sm = StateMachine("idle")
        sm.add_transition("idle", "active", "go", action=lambda: calls.append(1))
        sm.trigger("go")
        assert calls == [1]

    def test_history_recorded(self):
        sm = StateMachine("a")
        sm.add_transition("a", "b", "ab")
        sm.add_transition("b", "c", "bc")
        sm.trigger("ab")
        sm.trigger("bc")
        h = sm.history
        assert len(h) == 2
        assert h[0].from_state == "a" and h[0].to_state == "b"
        assert h[1].from_state == "b" and h[1].to_state == "c"

    def test_can_trigger_true(self):
        sm = StateMachine("idle")
        sm.add_transition("idle", "active", "start")
        assert sm.can_trigger("start") is True

    def test_can_trigger_false(self):
        sm = StateMachine("idle")
        assert sm.can_trigger("unknown") is False

    def test_can_trigger_guard_false(self):
        sm = StateMachine("idle")
        sm.add_transition("idle", "active", "go", guard=lambda: False)
        assert sm.can_trigger("go") is False

    def test_available_triggers(self):
        sm = StateMachine("idle")
        sm.add_transition("idle", "a", "go_a")
        sm.add_transition("idle", "b", "go_b")
        sm.add_transition("a", "b", "next")
        triggers = sm.available_triggers()
        assert set(triggers) == {"go_a", "go_b"}

    def test_reset(self):
        sm = StateMachine("idle")
        sm.add_transition("idle", "active", "start")
        sm.trigger("start")
        assert sm.current_state == "active"
        sm.reset()
        assert sm.current_state == "idle"
        assert sm.history == []

    def test_states_set(self):
        sm = StateMachine("idle")
        sm.add_transition("idle", "active", "go")
        assert "idle" in sm.states
        assert "active" in sm.states

    def test_state_eq_string(self):
        s = State("active")
        assert s == "active"
        assert s != "inactive"
