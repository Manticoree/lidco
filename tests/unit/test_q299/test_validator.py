"""Tests for CommitValidator (Q299)."""
import unittest

from lidco.smartgit.validator import CommitValidator, ValidationResult


class TestCommitValidator(unittest.TestCase):
    def setUp(self):
        self.validator = CommitValidator()

    # -- validate -------------------------------------------------------

    def test_validate_good_message(self):
        result = self.validator.validate("feat: add login page")
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.valid)
        self.assertTrue(result.is_conventional)

    def test_validate_empty_message(self):
        result = self.validator.validate("")
        self.assertFalse(result.valid)
        self.assertIn("empty", result.issues[0].lower())

    def test_validate_whitespace_only(self):
        result = self.validator.validate("   ")
        self.assertFalse(result.valid)

    def test_validate_too_long_subject(self):
        msg = "feat: " + "x" * 200
        result = self.validator.validate(msg)
        self.assertFalse(result.valid)
        self.assertTrue(any("exceeds" in i for i in result.issues))

    def test_validate_non_conventional(self):
        result = self.validator.validate("just some random message")
        self.assertFalse(result.valid)
        self.assertFalse(result.is_conventional)

    # -- check_conventional ---------------------------------------------

    def test_check_conventional_true(self):
        self.assertTrue(self.validator.check_conventional("fix: typo"))

    def test_check_conventional_with_scope(self):
        self.assertTrue(self.validator.check_conventional("feat(auth): add OAuth"))

    def test_check_conventional_false(self):
        self.assertFalse(self.validator.check_conventional("random text"))

    def test_check_conventional_unknown_type(self):
        self.assertFalse(self.validator.check_conventional("zzzz: unknown type"))

    # -- check_scope ----------------------------------------------------

    def test_check_scope_allowed(self):
        self.assertTrue(
            self.validator.check_scope("feat(auth): x", ["auth", "cli"])
        )

    def test_check_scope_not_allowed(self):
        self.assertFalse(
            self.validator.check_scope("feat(auth): x", ["cli", "core"])
        )

    def test_check_scope_absent_is_ok(self):
        self.assertTrue(
            self.validator.check_scope("feat: x", ["cli"])
        )

    def test_check_scope_non_conventional(self):
        self.assertFalse(
            self.validator.check_scope("random text", ["cli"])
        )

    # -- detect_breaking ------------------------------------------------

    def test_detect_breaking_bang(self):
        self.assertTrue(self.validator.detect_breaking("feat!: remove old API"))

    def test_detect_breaking_footer(self):
        self.assertTrue(
            self.validator.detect_breaking("feat: x\n\nBREAKING CHANGE: removed v1")
        )

    def test_detect_breaking_false(self):
        self.assertFalse(self.validator.detect_breaking("feat: add button"))

    def test_detect_breaking_hyphen_variant(self):
        self.assertTrue(
            self.validator.detect_breaking("feat: x\n\nBREAKING-CHANGE: y")
        )

    # -- issues ---------------------------------------------------------

    def test_issues_empty_list_for_valid(self):
        issues = self.validator.issues("feat: valid message")
        self.assertEqual(issues, [])

    def test_issues_non_empty_for_bad(self):
        issues = self.validator.issues("bad message no type")
        self.assertGreater(len(issues), 0)

    # -- custom allowed_types -------------------------------------------

    def test_custom_allowed_types(self):
        v = CommitValidator(allowed_types=["feat", "fix"])
        self.assertTrue(v.check_conventional("feat: ok"))
        self.assertFalse(v.check_conventional("docs: not allowed"))

    # -- result immutability -------------------------------------------

    def test_result_immutable(self):
        result = self.validator.validate("feat: ok")
        with self.assertRaises(AttributeError):
            result.valid = False  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
