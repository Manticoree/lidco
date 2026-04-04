"""Tests for hallucination.checker."""
import os
import unittest
from unittest.mock import patch
from lidco.hallucination.checker import FactChecker, Claim


class TestFactChecker(unittest.TestCase):

    def setUp(self):
        self.fc = FactChecker(project_root="/fake")

    def test_extract_file_claims(self):
        text = "Look at `src/lidco/cli/app.py` for details."
        claims = self.fc.extract_claims(text)
        file_claims = [c for c in claims if c.claim_type == "file_exists"]
        self.assertGreater(len(file_claims), 0)

    def test_extract_function_claims(self):
        text = "Call process_slash_command() to handle it."
        claims = self.fc.extract_claims(text)
        func_claims = [c for c in claims if c.claim_type == "function_exists"]
        self.assertGreater(len(func_claims), 0)

    def test_extract_import_claims(self):
        text = "You need to import lidco.core.config"
        claims = self.fc.extract_claims(text)
        import_claims = [c for c in claims if c.claim_type == "import_path"]
        self.assertGreater(len(import_claims), 0)

    def test_extract_no_claims(self):
        claims = self.fc.extract_claims("Hello world, nothing special.")
        self.assertEqual(len(claims), 0)

    @patch("os.path.isfile", return_value=True)
    def test_verify_file_exists(self, _):
        self.assertTrue(self.fc.verify_file("src/app.py"))

    @patch("os.path.isfile", return_value=False)
    def test_verify_file_not_exists(self, _):
        self.assertFalse(self.fc.verify_file("src/nonexistent.py"))

    @patch("os.path.isfile", return_value=True)
    def test_verify_claim_file(self, _):
        claim = Claim(text="File ref", claim_type="file_exists", target="src/app.py")
        result = self.fc.verify_claim(claim)
        self.assertTrue(result.verified)
        self.assertEqual(result.confidence, 1.0)

    @patch("os.path.isfile", return_value=False)
    def test_verify_claim_file_missing(self, _):
        claim = Claim(text="File ref", claim_type="file_exists", target="missing.py")
        result = self.fc.verify_claim(claim)
        self.assertFalse(result.verified)

    def test_verify_claim_general(self):
        claim = Claim(text="General claim", claim_type="general", target="")
        result = self.fc.verify_claim(claim)
        self.assertIsNone(result.verified)

    @patch("os.path.isfile", return_value=False)
    def test_check_full(self, _):
        text = "Check src/lidco/app.py for the handler."
        result = self.fc.check(text)
        self.assertGreater(result.failed_count + result.unchecked_count + result.verified_count, 0)

    def test_check_empty(self):
        result = self.fc.check("No references here.")
        self.assertEqual(result.overall_confidence, 1.0)

    def test_history(self):
        self.fc.check("Text 1")
        self.fc.check("Text 2")
        self.assertEqual(len(self.fc.history()), 2)


if __name__ == "__main__":
    unittest.main()
