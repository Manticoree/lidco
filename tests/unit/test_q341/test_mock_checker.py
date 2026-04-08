"""Tests for MockIntegrityChecker (Q341 Task 2)."""
from __future__ import annotations

import unittest


class TestFindSignatureDrift(unittest.TestCase):
    def setUp(self):
        from lidco.stability.mock_checker import MockIntegrityChecker
        self.c = MockIntegrityChecker()

    def test_empty_source_returns_empty(self):
        self.assertEqual(self.c.find_signature_drift(""), [])

    def test_return_value_assignment_detected(self):
        source = "mock_obj.return_value = 42\n"
        result = self.c.find_signature_drift(source)
        self.assertTrue(len(result) > 0)

    def test_magicmock_return_value_kwarg_detected(self):
        source = "m = MagicMock(return_value={'key': 'val'})\n"
        result = self.c.find_signature_drift(source)
        self.assertTrue(len(result) > 0)

    def test_line_number_accurate(self):
        source = "\n\nmock_obj.return_value = 'x'\n"
        result = self.c.find_signature_drift(source)
        self.assertEqual(result[0]["line"], 3)

    def test_no_drift_in_clean_code(self):
        source = "x = 1\ny = 2\n"
        result = self.c.find_signature_drift(source)
        self.assertEqual(result, [])

    def test_patch_with_return_value_detected(self):
        source = "with patch('module.Cls', return_value=None) as m:\n    pass\n"
        result = self.c.find_signature_drift(source)
        self.assertTrue(len(result) > 0)


class TestFindUnusedMocks(unittest.TestCase):
    def setUp(self):
        from lidco.stability.mock_checker import MockIntegrityChecker
        self.c = MockIntegrityChecker()

    def test_empty_source_returns_empty(self):
        self.assertEqual(self.c.find_unused_mocks(""), [])

    def test_used_mock_not_flagged(self):
        source = (
            "def test_something():\n"
            "    m = MagicMock()\n"
            "    result = m.call()\n"
            "    assert result is not None\n"
        )
        result = self.c.find_unused_mocks(source)
        self.assertFalse(any(r["mock_name"] == "m" for r in result))

    def test_unused_mock_flagged(self):
        source = (
            "def test_unused():\n"
            "    unused_mock = MagicMock()\n"
        )
        result = self.c.find_unused_mocks(source)
        self.assertTrue(any(r["mock_name"] == "unused_mock" for r in result))

    def test_suggestion_mentions_mock_name(self):
        source = (
            "def test_something():\n"
            "    orphan = MagicMock()\n"
        )
        result = self.c.find_unused_mocks(source)
        item = next(r for r in result if r["mock_name"] == "orphan")
        self.assertIn("orphan", item["suggestion"])

    def test_mock_used_in_assert_not_flagged(self):
        source = (
            "def test_assert():\n"
            "    m = MagicMock()\n"
            "    m.assert_called_once()\n"
        )
        result = self.c.find_unused_mocks(source)
        self.assertFalse(any(r["mock_name"] == "m" for r in result))


class TestDetectOverMocking(unittest.TestCase):
    def setUp(self):
        from lidco.stability.mock_checker import MockIntegrityChecker
        self.c = MockIntegrityChecker()

    def test_empty_source_returns_empty(self):
        self.assertEqual(self.c.detect_over_mocking(""), [])

    def test_few_mocks_not_flagged(self):
        source = (
            "def test_few():\n"
            "    a = MagicMock()\n"
            "    b = MagicMock()\n"
        )
        result = self.c.detect_over_mocking(source)
        self.assertEqual(result, [])

    def test_over_five_mocks_flagged(self):
        mocks = "\n".join(f"    m{i} = MagicMock()" for i in range(6))
        source = f"def test_heavy():\n{mocks}\n"
        result = self.c.detect_over_mocking(source)
        self.assertTrue(any(r["test_name"] == "test_heavy" for r in result))

    def test_mock_count_reported_correctly(self):
        mocks = "\n".join(f"    m{i} = MagicMock()" for i in range(6))
        source = f"def test_heavy():\n{mocks}\n"
        result = self.c.detect_over_mocking(source)
        item = next(r for r in result if r["test_name"] == "test_heavy")
        self.assertEqual(item["mock_count"], 6)

    def test_non_test_function_not_flagged(self):
        mocks = "\n".join(f"    m{i} = MagicMock()" for i in range(6))
        source = f"def helper():\n{mocks}\n"
        result = self.c.detect_over_mocking(source)
        self.assertEqual(result, [])

    def test_suggestion_mentions_test_name(self):
        mocks = "\n".join(f"    m{i} = MagicMock()" for i in range(6))
        source = f"def test_bloated():\n{mocks}\n"
        result = self.c.detect_over_mocking(source)
        item = next(r for r in result if r["test_name"] == "test_bloated")
        self.assertIn("test_bloated", item["suggestion"])


class TestCheckSignatureMatch(unittest.TestCase):
    def setUp(self):
        from lidco.stability.mock_checker import MockIntegrityChecker
        self.c = MockIntegrityChecker()

    def test_empty_specs_returns_empty(self):
        self.assertEqual(self.c.check_signature_match([]), [])

    def test_unimportable_class_returns_low_severity(self):
        specs = [
            {
                "mock_target": "my_mock",
                "spec_class": "nonexistent.module.Cls",
                "methods": ["do_thing"],
            }
        ]
        result = self.c.check_signature_match(specs)
        self.assertTrue(any(r["severity"] == "LOW" for r in result))

    def test_no_spec_class_skipped(self):
        specs = [{"mock_target": "m", "spec_class": "", "methods": []}]
        result = self.c.check_signature_match(specs)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
