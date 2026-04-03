"""Tests for PatternDetector (Q248)."""
from __future__ import annotations

import unittest

from lidco.conversation.pattern_detector import PatternDetector


class TestDetectLoops(unittest.TestCase):
    def test_no_loops(self):
        msgs = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]
        self.assertEqual(PatternDetector(msgs).detect_loops(), [])

    def test_detects_loop(self):
        msgs = [
            {"role": "user", "content": "fix it"},
            {"role": "assistant", "content": "done"},
            {"role": "user", "content": "fix it"},
        ]
        loops = PatternDetector(msgs).detect_loops()
        self.assertEqual(len(loops), 1)
        self.assertEqual(loops[0]["type"], "loop")
        self.assertEqual(loops[0]["indices"], [0, 2])

    def test_window_limits(self):
        msgs = [{"role": "user", "content": "same"}] * 2
        # window=1 means only look 1 back
        loops = PatternDetector(msgs).detect_loops(window=1)
        self.assertEqual(len(loops), 1)

    def test_empty_content_ignored(self):
        msgs = [{"role": "user", "content": ""}, {"role": "user", "content": ""}]
        self.assertEqual(PatternDetector(msgs).detect_loops(), [])

    def test_no_messages(self):
        self.assertEqual(PatternDetector([]).detect_loops(), [])


class TestDetectDeadEnds(unittest.TestCase):
    def test_empty_response(self):
        msgs = [
            {"role": "user", "content": "do something"},
            {"role": "assistant", "content": ""},
        ]
        dead = PatternDetector(msgs).detect_dead_ends()
        self.assertEqual(dead, [0])

    def test_error_response(self):
        msgs = [
            {"role": "user", "content": "run cmd"},
            {"role": "assistant", "content": "Error: something broke"},
        ]
        dead = PatternDetector(msgs).detect_dead_ends()
        self.assertEqual(dead, [0])

    def test_no_dead_ends(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        self.assertEqual(PatternDetector(msgs).detect_dead_ends(), [])

    def test_empty(self):
        self.assertEqual(PatternDetector([]).detect_dead_ends(), [])


class TestDetectExcessiveRetries(unittest.TestCase):
    def test_no_retries(self):
        msgs = [{"role": "user", "content": "hi"}]
        self.assertEqual(PatternDetector(msgs).detect_excessive_retries(), [])

    def test_detects_retries(self):
        msgs = [
            {"role": "assistant", "content": "x", "tool_calls": ["read"]},
            {"role": "assistant", "content": "x", "tool_calls": ["read"]},
            {"role": "assistant", "content": "x", "tool_calls": ["read"]},
            {"role": "assistant", "content": "x", "tool_calls": ["read"]},
        ]
        retries = PatternDetector(msgs).detect_excessive_retries(threshold=3)
        self.assertEqual(len(retries), 1)
        self.assertEqual(retries[0]["tool"], "read")
        self.assertEqual(retries[0]["count"], 4)

    def test_below_threshold(self):
        msgs = [
            {"role": "assistant", "content": "x", "tool_calls": ["read"]},
            {"role": "assistant", "content": "x", "tool_calls": ["read"]},
        ]
        self.assertEqual(PatternDetector(msgs).detect_excessive_retries(threshold=3), [])

    def test_dict_tool_calls(self):
        msgs = [
            {"role": "assistant", "content": "x", "tool_calls": [{"name": "write"}]},
            {"role": "assistant", "content": "x", "tool_calls": [{"name": "write"}]},
            {"role": "assistant", "content": "x", "tool_calls": [{"name": "write"}]},
            {"role": "assistant", "content": "x", "tool_calls": [{"name": "write"}]},
        ]
        retries = PatternDetector(msgs).detect_excessive_retries(threshold=3)
        self.assertEqual(len(retries), 1)
        self.assertEqual(retries[0]["tool"], "write")


class TestDetectAll(unittest.TestCase):
    def test_combines_alerts(self):
        msgs = [
            {"role": "user", "content": "fix"},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "fix"},
        ]
        alerts = PatternDetector(msgs).detect_all()
        types = {a["type"] for a in alerts}
        self.assertIn("loop", types)
        self.assertIn("dead_end", types)

    def test_empty(self):
        self.assertEqual(PatternDetector([]).detect_all(), [])


class TestSummary(unittest.TestCase):
    def test_clean(self):
        msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        self.assertEqual(PatternDetector(msgs).summary(), "No problematic patterns detected.")

    def test_with_issues(self):
        msgs = [
            {"role": "user", "content": "fix"},
            {"role": "assistant", "content": ""},
        ]
        s = PatternDetector(msgs).summary()
        self.assertIn("Detected", s)
        self.assertIn("dead_end", s)


if __name__ == "__main__":
    unittest.main()
