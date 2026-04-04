"""Tests for lidco.branches.strategy."""
from __future__ import annotations

import unittest

from lidco.branches.strategy import BranchStrategy2, VALID_STRATEGIES


class TestBranchStrategy2Init(unittest.TestCase):
    def test_default_strategy(self):
        s = BranchStrategy2()
        self.assertEqual(s.strategy, "github-flow")

    def test_valid_strategies_list(self):
        self.assertIn("gitflow", VALID_STRATEGIES)
        self.assertIn("github-flow", VALID_STRATEGIES)
        self.assertIn("trunk-based", VALID_STRATEGIES)


class TestSetStrategy(unittest.TestCase):
    def setUp(self):
        self.s = BranchStrategy2()

    def test_set_gitflow(self):
        self.s.set_strategy("gitflow")
        self.assertEqual(self.s.strategy, "gitflow")

    def test_set_trunk_based(self):
        self.s.set_strategy("trunk-based")
        self.assertEqual(self.s.strategy, "trunk-based")

    def test_set_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.s.set_strategy("unknown")

    def test_set_empty_raises(self):
        with self.assertRaises(ValueError):
            self.s.set_strategy("")


class TestValidateName(unittest.TestCase):
    def setUp(self):
        self.s = BranchStrategy2()

    def test_github_flow_feature_valid(self):
        self.assertTrue(self.s.validate_name("feature/my-thing"))

    def test_github_flow_fix_valid(self):
        self.assertTrue(self.s.validate_name("fix/bug-123"))

    def test_github_flow_invalid_prefix(self):
        self.assertFalse(self.s.validate_name("hotfix/something"))

    def test_github_flow_no_prefix(self):
        self.assertFalse(self.s.validate_name("my-branch"))

    def test_gitflow_hotfix_valid(self):
        self.s.set_strategy("gitflow")
        self.assertTrue(self.s.validate_name("hotfix/urgent-fix"))

    def test_trunk_based_short_valid(self):
        self.s.set_strategy("trunk-based")
        self.assertTrue(self.s.validate_name("short/quick-fix"))

    def test_trunk_based_feature_invalid(self):
        self.s.set_strategy("trunk-based")
        self.assertFalse(self.s.validate_name("feature/long-lived"))

    def test_uppercase_invalid(self):
        self.assertFalse(self.s.validate_name("feature/MyFeature"))


class TestAutoCreate(unittest.TestCase):
    def setUp(self):
        self.s = BranchStrategy2()

    def test_create_feature(self):
        result = self.s.auto_create("feature", "my thing")
        self.assertEqual(result, "feature/my-thing")

    def test_create_fix(self):
        result = self.s.auto_create("fix", "bug-123")
        self.assertEqual(result, "fix/bug-123")

    def test_sanitises_special_chars(self):
        result = self.s.auto_create("feature", "Hello World!!!")
        self.assertTrue(result.startswith("feature/"))
        self.assertNotIn(" ", result)
        self.assertNotIn("!", result)

    def test_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            self.s.auto_create("hotfix", "thing")

    def test_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.s.auto_create("feature", "!!!")

    def test_gitflow_hotfix(self):
        self.s.set_strategy("gitflow")
        result = self.s.auto_create("hotfix", "urgent")
        self.assertEqual(result, "hotfix/urgent")


class TestNamingRulesAndPrefixes(unittest.TestCase):
    def setUp(self):
        self.s = BranchStrategy2()

    def test_naming_rules_keys(self):
        rules = self.s.naming_rules()
        self.assertIn("strategy", rules)
        self.assertIn("pattern", rules)
        self.assertIn("protected", rules)
        self.assertIn("prefixes", rules)

    def test_naming_rules_strategy_matches(self):
        self.s.set_strategy("gitflow")
        rules = self.s.naming_rules()
        self.assertEqual(rules["strategy"], "gitflow")

    def test_allowed_prefixes_has_feature(self):
        prefixes = self.s.allowed_prefixes()
        self.assertIn("feature/", prefixes)

    def test_custom_prefix_included(self):
        s = BranchStrategy2(_custom_prefixes=["custom/"])
        prefixes = s.allowed_prefixes()
        self.assertIn("custom/", prefixes)


if __name__ == "__main__":
    unittest.main()
