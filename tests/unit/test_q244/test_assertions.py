"""Tests for AssertionEngine (Q244)."""
from __future__ import annotations

import unittest

from lidco.conversation.assertions import AssertionEngine, AssertionResult


def _sample_messages() -> list[dict]:
    return [
        {"role": "user", "content": "Hello world"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "a" * 5000},
    ]


class TestAssertContains(unittest.TestCase):
    def test_contains_found(self):
        ae = AssertionEngine(_sample_messages())
        self.assertTrue(ae.assert_contains(0, "Hello"))

    def test_contains_not_found(self):
        ae = AssertionEngine(_sample_messages())
        self.assertFalse(ae.assert_contains(0, "Goodbye"))

    def test_contains_empty_turn(self):
        ae = AssertionEngine(_sample_messages())
        self.assertFalse(ae.assert_contains(2, "anything"))

    def test_contains_invalid_turn(self):
        ae = AssertionEngine(_sample_messages())
        self.assertFalse(ae.assert_contains(99, "x"))

    def test_contains_negative_turn(self):
        ae = AssertionEngine(_sample_messages())
        self.assertFalse(ae.assert_contains(-1, "x"))


class TestAssertRole(unittest.TestCase):
    def test_role_matches(self):
        ae = AssertionEngine(_sample_messages())
        self.assertTrue(ae.assert_role(0, "user"))

    def test_role_mismatch(self):
        ae = AssertionEngine(_sample_messages())
        self.assertFalse(ae.assert_role(0, "assistant"))

    def test_role_invalid_turn(self):
        ae = AssertionEngine(_sample_messages())
        self.assertFalse(ae.assert_role(99, "user"))


class TestAssertTokenCount(unittest.TestCase):
    def test_within_limit(self):
        ae = AssertionEngine(_sample_messages())
        self.assertTrue(ae.assert_token_count(0, 100))

    def test_exceeds_limit(self):
        ae = AssertionEngine(_sample_messages())
        self.assertFalse(ae.assert_token_count(3, 10))

    def test_at_exact_limit(self):
        # 5000 chars / 4 = 1250 tokens
        ae = AssertionEngine(_sample_messages())
        self.assertTrue(ae.assert_token_count(3, 1250))

    def test_invalid_turn(self):
        ae = AssertionEngine(_sample_messages())
        self.assertFalse(ae.assert_token_count(99, 100))


class TestAssertNoEmptyTurns(unittest.TestCase):
    def test_has_empty(self):
        ae = AssertionEngine(_sample_messages())
        passed, indices = ae.assert_no_empty_turns()
        self.assertFalse(passed)
        self.assertIn(2, indices)

    def test_no_empty(self):
        msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        ae = AssertionEngine(msgs)
        passed, indices = ae.assert_no_empty_turns()
        self.assertTrue(passed)
        self.assertEqual(indices, [])

    def test_all_empty(self):
        msgs = [{"role": "user", "content": ""}, {"role": "assistant", "content": ""}]
        ae = AssertionEngine(msgs)
        passed, indices = ae.assert_no_empty_turns()
        self.assertFalse(passed)
        self.assertEqual(len(indices), 2)


class TestRunAll(unittest.TestCase):
    def test_run_contains(self):
        ae = AssertionEngine(_sample_messages())
        results = ae.run_all([{"type": "contains", "turn": 0, "value": "Hello"}])
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].passed)

    def test_run_role(self):
        ae = AssertionEngine(_sample_messages())
        results = ae.run_all([{"type": "role", "turn": 1, "value": "assistant"}])
        self.assertTrue(results[0].passed)

    def test_run_token_count(self):
        ae = AssertionEngine(_sample_messages())
        results = ae.run_all([{"type": "token_count", "turn": 3, "value": 10}])
        self.assertFalse(results[0].passed)

    def test_run_no_empty(self):
        ae = AssertionEngine(_sample_messages())
        results = ae.run_all([{"type": "no_empty"}])
        self.assertFalse(results[0].passed)

    def test_run_unknown_type(self):
        ae = AssertionEngine(_sample_messages())
        results = ae.run_all([{"type": "bogus"}])
        self.assertFalse(results[0].passed)
        self.assertIn("unknown", results[0].details)

    def test_run_multiple(self):
        ae = AssertionEngine(_sample_messages())
        assertions = [
            {"type": "contains", "turn": 0, "value": "Hello"},
            {"type": "role", "turn": 0, "value": "user"},
        ]
        results = ae.run_all(assertions)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.passed for r in results))

    def test_result_is_dataclass(self):
        ae = AssertionEngine(_sample_messages())
        results = ae.run_all([{"type": "contains", "turn": 0, "value": "Hello"}])
        self.assertIsInstance(results[0], AssertionResult)

    def test_empty_assertions_list(self):
        ae = AssertionEngine(_sample_messages())
        results = ae.run_all([])
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
