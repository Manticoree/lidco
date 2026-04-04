"""Tests for lidco.verify.logic — LogicVerifier."""
from __future__ import annotations

import unittest

from lidco.verify.logic import LogicVerifier, LogicResult


class TestLogicVerifier(unittest.TestCase):
    def setUp(self):
        self.v = LogicVerifier()

    # -- check_circular --------------------------------------------------

    def test_no_circular_for_unique_statements(self):
        issues = self.v.check_circular(["A is true", "B follows from A"])
        self.assertEqual(issues, [])

    def test_detect_duplicate_statement(self):
        issues = self.v.check_circular(["A is true", "B is new", "A is true"])
        self.assertEqual(len(issues), 1)
        self.assertIn("duplicates", issues[0])

    def test_circular_case_insensitive(self):
        issues = self.v.check_circular(["Hello world", "HELLO WORLD"])
        self.assertEqual(len(issues), 1)

    # -- check_syllogism -------------------------------------------------

    def test_valid_syllogism(self):
        self.assertTrue(
            self.v.check_syllogism(
                "All humans are mortal",
                "Socrates is a human",
                "Socrates is mortal",
            )
        )

    def test_invalid_syllogism_missing_word(self):
        self.assertFalse(
            self.v.check_syllogism(
                "All cats are animals",
                "Dogs are pets",
                "Elephants are large",
            )
        )

    def test_syllogism_short_words_ignored(self):
        # Words shorter than 3 chars are not checked
        self.assertTrue(
            self.v.check_syllogism("A is B", "C is D", "X is Y")
        )

    # -- find_gaps -------------------------------------------------------

    def test_no_gaps_when_linked(self):
        chain = ["The server crashed", "The crash caused downtime"]
        gaps = self.v.find_gaps(chain)
        self.assertEqual(gaps, [])

    def test_detect_gap_no_shared_vocab(self):
        chain = ["The server crashed", "Bananas are yellow"]
        gaps = self.v.find_gaps(chain)
        self.assertEqual(len(gaps), 1)
        self.assertIn("Gap", gaps[0])

    def test_find_gaps_empty_chain(self):
        self.assertEqual(self.v.find_gaps([]), [])

    def test_find_gaps_single_item(self):
        self.assertEqual(self.v.find_gaps(["only one"]), [])

    # -- verify ----------------------------------------------------------

    def test_verify_valid_chain(self):
        stmts = ["Function returns data", "Data is validated"]
        result = self.v.verify(stmts)
        self.assertIsInstance(result, LogicResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.issues, [])

    def test_verify_detects_issues(self):
        stmts = ["Function returns data", "Bananas are tasty", "Function returns data"]
        result = self.v.verify(stmts)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.issues), 0)

    def test_logic_result_is_frozen(self):
        result = LogicResult(is_valid=True, issues=[])
        with self.assertRaises(AttributeError):
            result.is_valid = False  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
