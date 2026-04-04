"""Tests for ToolCacheAdvisor."""
from __future__ import annotations

import unittest

from lidco.tool_opt.cache_advisor import ToolCacheAdvisor


class TestToolCacheAdvisor(unittest.TestCase):
    def setUp(self):
        self.ca = ToolCacheAdvisor()

    def test_record_call(self):
        self.ca.record_call("Read", {"path": "a.py"}, "contents")
        self.assertEqual(len(self.ca.calls), 1)

    def test_record_call_defaults(self):
        self.ca.record_call("Edit")
        tool, args, result = self.ca.calls[0]
        self.assertEqual(tool, "Edit")
        self.assertEqual(args, {})
        self.assertIsNone(result)

    def test_detect_repeated_none(self):
        self.ca.record_call("Read", {"path": "a.py"})
        self.assertEqual(self.ca.detect_repeated(), [])

    def test_detect_repeated_found(self):
        self.ca.record_call("Read", {"path": "a.py"}, "x")
        self.ca.record_call("Read", {"path": "a.py"}, "x")
        self.ca.record_call("Read", {"path": "a.py"}, "x")
        repeated = self.ca.detect_repeated()
        self.assertEqual(len(repeated), 1)
        tool, args, count = repeated[0]
        self.assertEqual(tool, "Read")
        self.assertEqual(count, 3)

    def test_detect_repeated_different_args(self):
        self.ca.record_call("Read", {"path": "a.py"})
        self.ca.record_call("Read", {"path": "b.py"})
        self.assertEqual(self.ca.detect_repeated(), [])

    def test_suggest_cache_empty(self):
        self.assertEqual(self.ca.suggest_cache(), [])

    def test_suggest_cache_with_repeats(self):
        self.ca.record_call("Read", {"path": "a.py"})
        self.ca.record_call("Read", {"path": "a.py"})
        suggestions = self.ca.suggest_cache()
        self.assertTrue(len(suggestions) >= 1)
        self.assertTrue(any("Cache" in s for s in suggestions))

    def test_suggest_cache_many_reads(self):
        for i in range(5):
            self.ca.record_call("Read", {"path": f"f{i}.py"})
        suggestions = self.ca.suggest_cache()
        self.assertTrue(any("read" in s.lower() for s in suggestions))

    def test_estimate_savings_empty(self):
        s = self.ca.estimate_savings()
        self.assertEqual(s["total_calls"], 0)
        self.assertEqual(s["cacheable_calls"], 0)
        self.assertEqual(s["saved_ratio"], 0.0)

    def test_estimate_savings_with_repeats(self):
        self.ca.record_call("Read", {"path": "a.py"})
        self.ca.record_call("Read", {"path": "a.py"})
        self.ca.record_call("Edit", {"path": "a.py"})
        s = self.ca.estimate_savings()
        self.assertEqual(s["total_calls"], 3)
        self.assertEqual(s["cacheable_calls"], 1)
        self.assertGreater(s["saved_ratio"], 0)
        self.assertEqual(s["repeated_patterns"], 1)

    def test_estimate_savings_unique_calls(self):
        self.ca.record_call("Read", {"path": "a.py"})
        self.ca.record_call("Edit", {"path": "b.py"})
        s = self.ca.estimate_savings()
        self.assertEqual(s["unique_calls"], 2)
        self.assertEqual(s["cacheable_calls"], 0)


if __name__ == "__main__":
    unittest.main()
