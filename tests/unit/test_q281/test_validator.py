"""Tests for hallucination.validator."""
import os
import tempfile
import unittest
from lidco.hallucination.validator import ReferenceValidator


class TestReferenceValidator(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.validator = ReferenceValidator(project_root=self.tmpdir)
        # Create a test file
        self.test_file = os.path.join(self.tmpdir, "test.py")
        with open(self.test_file, "w") as f:
            f.write("def hello():\n    pass\n\ndef world():\n    pass\n")

    def test_validate_file_exists(self):
        r = self.validator.validate_file("test.py")
        self.assertTrue(r.valid)

    def test_validate_file_missing(self):
        r = self.validator.validate_file("nonexistent.py")
        self.assertFalse(r.valid)
        self.assertIn("not found", r.message.lower())

    def test_validate_line_valid(self):
        r = self.validator.validate_line("test.py", 1)
        self.assertTrue(r.valid)

    def test_validate_line_out_of_range(self):
        r = self.validator.validate_line("test.py", 100)
        self.assertFalse(r.valid)

    def test_validate_line_file_missing(self):
        r = self.validator.validate_line("nope.py", 1)
        self.assertFalse(r.valid)

    def test_validate_snippet_found(self):
        r = self.validator.validate_snippet("test.py", "def hello():")
        self.assertTrue(r.valid)

    def test_validate_snippet_not_found(self):
        r = self.validator.validate_snippet("test.py", "def nonexistent():")
        self.assertFalse(r.valid)

    def test_validate_snippet_file_missing(self):
        r = self.validator.validate_snippet("nope.py", "def hello():")
        self.assertFalse(r.valid)

    def test_validate_function_found(self):
        r = self.validator.validate_function("test.py", "hello")
        self.assertTrue(r.valid)

    def test_validate_function_not_found(self):
        r = self.validator.validate_function("test.py", "missing_func")
        self.assertFalse(r.valid)

    def test_validate_function_file_missing(self):
        r = self.validator.validate_function("nope.py", "hello")
        self.assertFalse(r.valid)

    def test_checks_list(self):
        self.validator.validate_file("test.py")
        self.validator.validate_file("nope.py")
        self.assertEqual(len(self.validator.checks()), 2)

    def test_validity_ratio(self):
        self.validator.validate_file("test.py")
        self.validator.validate_file("nope.py")
        self.assertEqual(self.validator.validity_ratio(), 0.5)

    def test_validity_ratio_empty(self):
        self.assertEqual(self.validator.validity_ratio(), 0.0)

    def test_summary(self):
        self.validator.validate_file("test.py")
        s = self.validator.summary()
        self.assertEqual(s["valid"], 1)


if __name__ == "__main__":
    unittest.main()
