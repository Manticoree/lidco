"""Tests for ReplayEngine (Q244)."""
from __future__ import annotations

import unittest

from lidco.conversation.replay_engine import ReplayEngine


def _sample_messages() -> list[dict]:
    return [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I'm fine, thanks!"},
    ]


class TestReplayEngineInit(unittest.TestCase):
    def test_initial_cursor_is_minus_one(self):
        engine = ReplayEngine(_sample_messages())
        self.assertEqual(engine.current_turn, -1)

    def test_total_turns(self):
        engine = ReplayEngine(_sample_messages())
        self.assertEqual(engine.total_turns, 4)

    def test_empty_messages(self):
        engine = ReplayEngine([])
        self.assertEqual(engine.total_turns, 0)

    def test_does_not_mutate_input(self):
        msgs = _sample_messages()
        ReplayEngine(msgs)
        self.assertEqual(len(msgs), 4)


class TestStepForward(unittest.TestCase):
    def test_step_forward_first(self):
        engine = ReplayEngine(_sample_messages())
        msg = engine.step_forward()
        self.assertIsNotNone(msg)
        self.assertEqual(msg["role"], "user")
        self.assertEqual(engine.current_turn, 0)

    def test_step_forward_twice(self):
        engine = ReplayEngine(_sample_messages())
        engine.step_forward()
        msg = engine.step_forward()
        self.assertEqual(msg["role"], "assistant")
        self.assertEqual(engine.current_turn, 1)

    def test_step_forward_past_end(self):
        engine = ReplayEngine([{"role": "user", "content": "hi"}])
        engine.step_forward()
        result = engine.step_forward()
        self.assertIsNone(result)

    def test_step_forward_returns_copy(self):
        msgs = _sample_messages()
        engine = ReplayEngine(msgs)
        msg = engine.step_forward()
        msg["role"] = "modified"
        next_msg = engine.step_forward()
        self.assertEqual(next_msg["role"], "assistant")


class TestStepBackward(unittest.TestCase):
    def test_backward_from_start(self):
        engine = ReplayEngine(_sample_messages())
        result = engine.step_backward()
        self.assertIsNone(result)

    def test_backward_after_forward(self):
        engine = ReplayEngine(_sample_messages())
        engine.step_forward()
        engine.step_forward()
        msg = engine.step_backward()
        self.assertEqual(msg["role"], "user")
        self.assertEqual(engine.current_turn, 0)

    def test_backward_at_zero(self):
        engine = ReplayEngine(_sample_messages())
        engine.step_forward()
        result = engine.step_backward()
        self.assertIsNone(result)


class TestJumpTo(unittest.TestCase):
    def test_jump_to_valid(self):
        engine = ReplayEngine(_sample_messages())
        msg = engine.jump_to(2)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["content"], "How are you?")
        self.assertEqual(engine.current_turn, 2)

    def test_jump_to_negative(self):
        engine = ReplayEngine(_sample_messages())
        result = engine.jump_to(-1)
        self.assertIsNone(result)

    def test_jump_to_out_of_range(self):
        engine = ReplayEngine(_sample_messages())
        result = engine.jump_to(100)
        self.assertIsNone(result)


class TestModifyAndRerun(unittest.TestCase):
    def test_modify_replaces_message(self):
        engine = ReplayEngine(_sample_messages())
        new_msg = {"role": "user", "content": "Changed!"}
        remaining = engine.modify_and_rerun(1, new_msg)
        self.assertEqual(len(remaining), 3)
        self.assertEqual(remaining[0]["content"], "Changed!")

    def test_modify_invalid_turn(self):
        engine = ReplayEngine(_sample_messages())
        result = engine.modify_and_rerun(99, {"role": "user", "content": "x"})
        self.assertEqual(result, [])

    def test_modify_updates_cursor(self):
        engine = ReplayEngine(_sample_messages())
        engine.modify_and_rerun(2, {"role": "user", "content": "new"})
        self.assertEqual(engine.current_turn, 2)


class TestWhatIf(unittest.TestCase):
    def test_what_if_branches(self):
        engine = ReplayEngine(_sample_messages())
        alt = {"role": "user", "content": "Alternative"}
        branch = engine.what_if(2, alt)
        self.assertEqual(len(branch), 3)
        self.assertEqual(branch[2]["content"], "Alternative")

    def test_what_if_does_not_mutate(self):
        engine = ReplayEngine(_sample_messages())
        alt = {"role": "user", "content": "Alt"}
        engine.what_if(1, alt)
        self.assertEqual(engine.total_turns, 4)

    def test_what_if_invalid_turn(self):
        engine = ReplayEngine(_sample_messages())
        result = engine.what_if(-1, {"role": "user", "content": "x"})
        self.assertEqual(result, [])


class TestReset(unittest.TestCase):
    def test_reset_cursor(self):
        engine = ReplayEngine(_sample_messages())
        engine.step_forward()
        engine.step_forward()
        engine.reset()
        self.assertEqual(engine.current_turn, -1)


if __name__ == "__main__":
    unittest.main()
