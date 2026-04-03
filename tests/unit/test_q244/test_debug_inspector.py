"""Tests for DebugInspector (Q244)."""
from __future__ import annotations

import unittest

from lidco.conversation.debug_inspector import DebugInspector, MessageInspection


class TestInspect(unittest.TestCase):
    def setUp(self):
        self.inspector = DebugInspector()

    def test_basic_user_message(self):
        msg = {"role": "user", "content": "Hello world"}
        info = self.inspector.inspect(msg)
        self.assertEqual(info.role, "user")
        self.assertEqual(info.content_length, 11)
        self.assertFalse(info.has_tool_calls)
        self.assertEqual(info.tool_call_count, 0)
        self.assertTrue(info.has_content)

    def test_empty_content(self):
        msg = {"role": "assistant", "content": ""}
        info = self.inspector.inspect(msg)
        self.assertEqual(info.content_length, 0)
        self.assertFalse(info.has_content)

    def test_none_content(self):
        msg = {"role": "assistant", "content": None}
        info = self.inspector.inspect(msg)
        self.assertEqual(info.content_length, 0)
        self.assertFalse(info.has_content)

    def test_tool_calls(self):
        msg = {
            "role": "assistant",
            "content": "Let me help",
            "tool_calls": [{"id": "1", "function": {"name": "read"}}],
        }
        info = self.inspector.inspect(msg)
        self.assertTrue(info.has_tool_calls)
        self.assertEqual(info.tool_call_count, 1)

    def test_multiple_tool_calls(self):
        msg = {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
        }
        info = self.inspector.inspect(msg)
        self.assertEqual(info.tool_call_count, 3)

    def test_metadata_extracted(self):
        msg = {"role": "user", "content": "hi", "name": "Alice", "timestamp": 123}
        info = self.inspector.inspect(msg)
        self.assertIn("name", info.metadata)
        self.assertIn("timestamp", info.metadata)
        self.assertNotIn("role", info.metadata)

    def test_missing_role(self):
        msg = {"content": "orphan"}
        info = self.inspector.inspect(msg)
        self.assertEqual(info.role, "")

    def test_inspection_is_frozen(self):
        msg = {"role": "user", "content": "test"}
        info = self.inspector.inspect(msg)
        with self.assertRaises(AttributeError):
            info.role = "changed"


class TestInspectBatch(unittest.TestCase):
    def setUp(self):
        self.inspector = DebugInspector()

    def test_batch_returns_list(self):
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
        results = self.inspector.inspect_batch(msgs)
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], MessageInspection)

    def test_empty_batch(self):
        results = self.inspector.inspect_batch([])
        self.assertEqual(results, [])


class TestTokenEstimate(unittest.TestCase):
    def setUp(self):
        self.inspector = DebugInspector()

    def test_estimate(self):
        msg = {"content": "a" * 100}
        self.assertEqual(self.inspector.token_estimate(msg), 25)

    def test_empty_content(self):
        msg = {"content": ""}
        self.assertEqual(self.inspector.token_estimate(msg), 0)

    def test_none_content(self):
        msg = {"content": None}
        self.assertEqual(self.inspector.token_estimate(msg), 0)

    def test_missing_content(self):
        msg = {"role": "user"}
        self.assertEqual(self.inspector.token_estimate(msg), 0)


class TestTimingInfo(unittest.TestCase):
    def setUp(self):
        self.inspector = DebugInspector()

    def test_positions(self):
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "bb"},
            {"role": "user", "content": "ccc"},
        ]
        info = self.inspector.timing_info(msgs)
        self.assertEqual(info[0]["position"], "first")
        self.assertEqual(info[1]["position"], "middle")
        self.assertEqual(info[2]["position"], "last")

    def test_single_message(self):
        msgs = [{"role": "user", "content": "only"}]
        info = self.inspector.timing_info(msgs)
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0]["position"], "first")

    def test_two_messages(self):
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
        info = self.inspector.timing_info(msgs)
        self.assertEqual(info[0]["position"], "first")
        self.assertEqual(info[1]["position"], "last")

    def test_index_and_role(self):
        msgs = [{"role": "system", "content": "sys"}]
        info = self.inspector.timing_info(msgs)
        self.assertEqual(info[0]["index"], 0)
        self.assertEqual(info[0]["role"], "system")


if __name__ == "__main__":
    unittest.main()
